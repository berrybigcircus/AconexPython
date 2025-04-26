import xml.etree.ElementTree as ElTree  # for parsing xml
import datetime
from typing import Any
from urllib.parse import urlencode
from xml.etree.ElementTree import Element

import pandas  # for exporting to excel

from OAuth.APIcommon import getAPIResponse, convertDateTime, projectSelection, Project

workflowData = {
    "Document Number": [],
    "Title": [],
    "Revision": [],
    "Workflow Status": [],
    "Date In": [],
    "Step Name": [],
    "Step Outcome": [],
    "Date of Comments": [],
    "Comments": [],
    "Latest revision?": []
}

EXPORTFNAME = 'ExportedData.xlsx' #workbook to place the raw data into

def searchForDoc(docTrackingID) -> Element | None:
    searchTerm = "trackingid:" + docTrackingID
    parameters = {"search_type": "PAGED",  # PAGED, meaning return results by "pages" of variable size.
                  "return_fields": "trackingid,docno,title,revision,reviewstatus,reviewSource",
                  "search_query": searchTerm
                  }

    headers = {'Authorization': bearer}
    url = PROJECTURL + "/register?" + urlencode(parameters)

    xml = getAPIResponse(url, headers, "searching for document " + docTrackingID)
    docXml = ElTree.fromstring(xml.strip()).find('SearchResults/') #there is only one doc returned so can use find rather than findall
    return docXml

def searchForWorkflow(wfReviewsXml, trackingId) -> list[Any]:
    #find the document's workflow reviews, using the tracking id
    wfReviewsXml = [wfxml for wfxml in wfReviewsXml if wfxml.find('DocumentTrackingId').text == trackingId]

    wfReviewsXml = sorted(wfReviewsXml, key=lambda step: (step.find('DateIn').text is None, step.find('DateIn').text)) #ensure comments are sorted by date (earliest to latest)
    return wfReviewsXml

def addWorkflowData(wfReviewsXml, currentRev=""):
    prevnum = None

    for reviewXml in wfReviewsXml: #in case it's been in multiple reviews
        #we need to run this every time because we need to know the doc's current doc number, not what it was in the WF - this is in case the number changes (WISBECH)
        docTrackingID = reviewXml.find('DocumentTrackingId').text
        docxml = searchForDoc(docTrackingID)

        docnum = docxml.find('DocumentNumber').text
        if prevnum is not None and docnum != prevnum:
            currentRev = ""
        wfstatus = reviewXml.find('WorkflowStatus').text
        docRev = reviewXml.find('DocumentRevision').text
        stepstatus = reviewXml.find('StepStatus').text
        stepoutcome = reviewXml.find('StepOutcome').text

        # remove workflow steps that are forecast or terminated, or skipped because the workflow ended early
        if stepstatus in ["Forecast", "Terminated"] or wfstatus == "Terminated" or stepoutcome == "None":
            continue

        workflowData["Document Number"].append(docnum)
        workflowData["Title"].append(reviewXml.find('DocumentTitle').text)

        #workflowData["WorkflowNumber"].append(reviewXml.find('WorkflowNumber').text)
        workflowData["Revision"].append(docRev)
        workflowData["Workflow Status"].append(wfstatus)
        workflowData["Date In"].append(convertDateTime(reviewXml.find('DateIn').text,"%d/%m/%Y"))
        workflowData["Step Name"].append(reviewXml.find('StepName').text)
        workflowData["Step Outcome"].append(stepoutcome)
        workflowData["Date of Comments"].append(convertDateTime(reviewXml.find('DateCompleted').text,"%d/%m/%Y"))
        workflowData["Comments"].append(reviewXml.find('Comments').text)

        if currentRev == "":
            currentRev = docxml.find('Revision').text if docxml is not None else ""
        workflowData["Latest revision?"].append(docRev == currentRev)
        prevnum = docnum


def exportToExcel():
    #create sheet to write the project information
    projectinfo = {
        "Project Name": [projectname],
        "Date Generated": [datetime.datetime.today().strftime('%d/%m/%Y')]
    }
    dataframe = pandas.DataFrame(data=projectinfo)
    with pandas.ExcelWriter(EXPORTFNAME, mode='a', if_sheet_exists='replace') as writer:
        dataframe.to_excel(writer,
                           sheet_name="ProjectInfo",
                           header= True,
                           startrow = 0,
                           index=False) #no index col

    # export the comment datas into excel
    dataframe = pandas.DataFrame(data=workflowData)  # convert into pandas data frame for exporting
    with pandas.ExcelWriter(EXPORTFNAME,mode='a', if_sheet_exists='replace') as writer:
        dataframe.to_excel(writer,
                           sheet_name="RawData",
                           header= True,
                           startrow = 0,
                           index=False) #no index col
    print("     Workflow data added to ExportedData.xlsx")

def main(passedBearer, env, project: Project, inputUseTextFile : str):
    global bearer
    bearer = passedBearer
    global aconexEnv
    aconexEnv = env

    global projectname
    projectname, chosenProjectID = project.getProject()
    global PROJECTURL
    PROJECTURL = "https://api.aconex.com/api/projects/" + chosenProjectID  # url of the chosen project (using project id)

    if inputUseTextFile == "y":
        genTrackerTextFile()
    else:
        print("Generating a tracker for all documents " + projectname)
        #Generate a tracker for ALL documents
        wfReviewsXml = getAllWorkflows()
        addWorkflowData(wfReviewsXml)
        exportToExcel()

def getAllWorkflows() -> list[Element]:
    headers = {'Authorization': bearer}
    url = PROJECTURL + "/workflows?page_size=100000" #can you believe it will let you do 100,000 page size, DOUBT - watch this break
    xml = getAPIResponse(url, headers, "getting workflow information") #initial call
    totalPages : int = int(ElTree.fromstring(xml.strip()).get('TotalPages'))
    wfReviewsXml = ElTree.fromstring(xml)

    currentPageNum = 1
    while currentPageNum < totalPages:
        url = PROJECTURL + "/workflows?page_size=100000&page_number=" + str(currentPageNum)
        xml = getAPIResponse(url, headers, "getting workflow information (page = %d)" % currentPageNum)
        wfReviewsXml.extend(ElTree.fromstring(xml))

        currentPageNum += 1

    wfReviewsXml = sorted(wfReviewsXml.findall('SearchResults/Workflow'), key=lambda step: step.find('DocumentNumber').text)
    return wfReviewsXml

#Generate a tracker only on the selected documents
def genTrackerTextFile():
    #get the documents to search for using the input text file
    file = open("docsList.txt", "r")
    textLines = [line.rstrip() for line in file]
    textLines = textLines[1::]  # remove top info line
    file.close()

    wfReviewsXml = getAllWorkflows()

    for iLine in textLines:
        #search up the user's doc number
        docXml = searchForDoc(iLine)

        # if 0 search results
        if docXml == None:
            print("Error - Document could not be found in the register with the number %s" % iLine)
            continue

        docTitle = docXml.find('Title').text
        docRevision = docXml.find('Revision').text
        print("Document %s - %s (Current Rev = %s)" % (iLine, docTitle, docRevision))

        docTrackingID = docXml.find('TrackingId').text
        docWorkflowsXml = searchForWorkflow(wfReviewsXml, docTrackingID)
        addWorkflowData(docWorkflowsXml, docRevision)

    exportToExcel()