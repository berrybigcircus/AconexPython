import xml.etree.ElementTree as ElTree  # for parsing xml
import datetime
from typing import Any
from urllib.parse import urlencode
from xml.etree.ElementTree import Element

import pandas  # for exporting to excel

from OAuth.APIcommon import getAPIResponse, convertDateTimeStr
import OAuth.config as config

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
    "Workflow Outcome": [],
    "Latest revision?": [],
}

EXPORTFNAME = 'ExportedData.xlsx' #workbook to place the raw data into

def searchForDoc(searchTerm : str) -> Element | None:
    parameters = {"search_type": "PAGED",  # PAGED, meaning return results by "pages" of variable size.
                  "return_fields": "trackingid,docno,title,revision,reviewstatus,reviewSource",
                  "search_query": searchTerm
                  }

    headers = {'Authorization': config.bearer()}
    url = config.projecturl() + "/register?" + urlencode(parameters)

    xml = getAPIResponse(url, headers, "searching for document " + searchTerm)
    docXml = ElTree.fromstring(xml.strip()).find('SearchResults/') #there is only one doc returned so can use find rather than findall
    return docXml

def searchForWorkflow(wfReviewsXml, trackingId) -> list[Any]:
    #find the document's workflow reviews, using the tracking id
    wfReviewsXml = [wfxml for wfxml in wfReviewsXml if wfxml.find('DocumentTrackingId').text == trackingId]

    wfReviewsXml = sorted(wfReviewsXml, key=lambda step: (step.find('DateIn').text is None, step.find('DateIn').text)) #ensure comments are sorted by date (earliest to latest)
    return wfReviewsXml

def addWorkflowData(wfReviewsXml, currentRev=""):
    prevID = None
    docreviewoutcome = ""

    for reviewXml in wfReviewsXml: #in case it's been in multiple reviews
        docTrackingID = reviewXml.find('DocumentTrackingId').text

        #we need to run this every time because we need to know the doc's current doc number, not what it was in the WF - this is in case the number changes (WISBECH)
        if prevID is None or docTrackingID != prevID:
            docxml = searchForDoc("trackingid:" + docTrackingID)
            docnum = docxml.find('DocumentNumber').text if docxml else reviewXml.find('DocumentNumber').text
            currentRev = docxml.find('Revision').text if docxml is not None else ""
            docreviewoutcome = docxml.find('ReviewStatus').text if docxml is not None else ""

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
        workflowData["Date In"].append(convertDateTimeStr(reviewXml.find('DateIn').text, "%d/%m/%Y"))
        workflowData["Step Name"].append(reviewXml.find('StepName').text)
        workflowData["Step Outcome"].append(stepoutcome)
        workflowData["Date of Comments"].append(convertDateTimeStr(reviewXml.find('DateCompleted').text, "%d/%m/%Y"))
        workflowData["Comments"].append(reviewXml.find('Comments').text)

        workflowData["Workflow Outcome"].append(docreviewoutcome)
        workflowData["Latest revision?"].append(docRev == currentRev)
        prevID = docTrackingID


def exportToExcel():
    #create sheet to write the project information
    projectinfo = {
        "Project Name": [config.project().projectName()],
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

def main(inputUseTextFile : str):
    if inputUseTextFile == "y":
        genTrackerTextFile()
    else:
        print("Generating a tracker for all documents " + config.project().projectName())
        #Generate a tracker for ALL documents
        wfReviewsXml = getAllWorkflows()
        addWorkflowData(wfReviewsXml)
        exportToExcel()

def getAllWorkflows() -> list[Element]:
    headers = {'Authorization': config.bearer()}
    url = config.projecturl() + "/workflows?page_size=100000" #can you believe it will let you do 100,000 page size, DOUBT - watch this break
    xml = getAPIResponse(url, headers, "getting workflow information") #initial call
    totalPages : int = int(ElTree.fromstring(xml.strip()).get('TotalPages'))
    wfReviewsXml = ElTree.fromstring(xml)

    currentPageNum = 1
    while currentPageNum < totalPages:
        url = config.projecturl() + "/workflows?page_size=100000&page_number=" + str(currentPageNum)
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
        docXml = searchForDoc("docno:"+ iLine)

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