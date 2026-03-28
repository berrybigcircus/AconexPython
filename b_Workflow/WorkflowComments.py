import datetime
import os
import xml.etree.ElementTree as ElTree  # for parsing xml
from typing import Any
from xml.etree.ElementTree import Element

import pandas  # for exporting to excel

from Setup.config import config
from Setup.Doc import searchForDoc

from Setup.APIcommon import getAPIResponse, convertDateTimeStr, cleanOrgName, importLastRun

import pathlib

workflowData = {
    "Document Number": [],
    "Title": [],
    "Revision": [],
    "Created by": [],
    "Workflow Number": [],
    "Workflow Status": [],
    "Date In": [],
    "Step Name": [],
    "Assigned to Org": [],
    "Step Outcome": [],
    "Date of Comments": [],
    "Comments": [],
    "Workflow Outcome": [],
    "Latest revision?": [],
}

def searchForWorkflow(wfReviewsXml, trackingId) -> list[Any]:
    #find the document's workflow reviews, using the tracking id
    wfReviewsXml = [wfxml for wfxml in wfReviewsXml if wfxml.find('DocumentTrackingId').text == trackingId]

    wfReviewsXml = sorted(wfReviewsXml, key=lambda step: (step.find('DateIn').text is None, step.find('DateIn').text)) #ensure comments are sorted by date (earliest to latest)
    return wfReviewsXml

def addWorkflowData(wfReviewsXml, currentRev=""):
    prevID = None
    docreviewoutcome = ""
    docstatus = ""
    createdby = ""
    skipcount = 0
    returnfields = "trackingid,docno,title,revision,author,reviewstatus,reviewSource,statusid"

    for reviewXml in wfReviewsXml: #in case it's been in multiple reviews
        docTrackingID = reviewXml.find('DocumentTrackingId').text

        #we need to run this every time because we need to know the doc's current doc number, not what it was in the WF - this is in case the number changes (WISBECH)
        if prevID is None or docTrackingID != prevID:
            docxml = searchForDoc(config, "trackingid:" + docTrackingID, returnfields)
            docnum = docxml.find('DocumentNumber').text if docxml else reviewXml.find('DocumentNumber').text
            createdby = cleanOrgName(docxml.find("Author").text) if docxml is not None else ""
            docstatus = docxml.find('DocumentStatus').text if docxml is not None else "No Longer In Use"
            currentRev = docxml.find('Revision').text if docxml is not None else ""
            docreviewoutcome = docxml.find('ReviewStatus').text if docxml is not None else ""

        wfstatus = reviewXml.find('WorkflowStatus').text
        wfnumber = reviewXml.find('WorkflowNumber').text
        docRev = reviewXml.find('DocumentRevision').text
        stepstatus = reviewXml.find('StepStatus').text
        stepoutcome = reviewXml.find('StepOutcome').text

        assigneesOrgsXML = reviewXml.findall('Assignees/Assignee/OrganizationName')


        # remove workflow steps that are forecast or terminated, or skipped because the workflow ended early
        # remove docs no longer in use
        if stepstatus in ["Forecast", "Terminated"] or wfstatus == "Terminated" or stepoutcome == "None" or docstatus == "No Longer In Use":
            prevID = docTrackingID
            skipcount +=1
            continue

        workflowData["Document Number"].append(docnum)
        workflowData["Title"].append(reviewXml.find('DocumentTitle').text)

        workflowData["Revision"].append(docRev)
        workflowData["Created by"].append(createdby)
        workflowData["Workflow Status"].append(wfstatus)
        workflowData["Workflow Number"].append(wfnumber)
        workflowData["Date In"].append(convertDateTimeStr(reviewXml.find('DateIn').text, "%d/%m/%Y %H:%M:%S"))
        workflowData["Step Name"].append(reviewXml.find('StepName').text)
        workflowData["Step Outcome"].append(stepoutcome)
        workflowData["Date of Comments"].append(convertDateTimeStr(reviewXml.find('DateCompleted').text, "%d/%m/%Y %H:%M:%S"))
        workflowData["Comments"].append(reviewXml.find('Comments').text)

        workflowData["Workflow Outcome"].append(docreviewoutcome)

        workflowData["Assigned to Org"].append("\n".join(set([cleanOrgName(orgxml.text) for orgxml in assigneesOrgsXML])))

        workflowData["Latest revision?"].append(docRev == currentRev)
        prevID = docTrackingID

    config.info("Skipped %d" % skipcount)
    config.debug(str(len(workflowData["Document Number"])))

def exportToExcel(fname: str, amend : bool):
    #TODO amend = True

    #create sheet to write the project information
    projectinfo = {
        "Project Name": [config.project().projectName()],
        "Date Generated": [datetime.datetime.today().strftime('%d/%m/%Y %H:%M')],
    }
    dataframe = pandas.DataFrame(data=projectinfo)
    if os.path.exists(fname):
        writer = pandas.ExcelWriter(fname, mode='a', engine='openpyxl', if_sheet_exists="replace")
    else:
        writer = pandas.ExcelWriter(fname, mode='w')

    dataframe.to_excel(writer,
           sheet_name="ProjectInfo",
           header= True,
           startrow = 0,
           index=False) #no index col

    # export the comment datas into excel
    dataframe = pandas.DataFrame(data=workflowData)  # convert into pandas data frame for exporting
    dataframe.to_excel(writer,
           sheet_name="RawData",
           header= True,
           startrow = 0,
           index=False) #no index col

    writer.close()
    config.info("     Workflow data added to ExportedData.xlsx")

def main(inputUseTextFile : str, forceAll : bool = False):
    global FOLDERPATH
    FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
    FILEPATH : str = FOLDERPATH + "\\Trackers\\" + config.project().projectCodePrefix() + "ExportedData.xlsx"

    if inputUseTextFile == "y":
        genTrackerTextFile()
    else:
        #Import the date the tracker was last ran
        lastrun : datetime.datetime = importLastRun(FILEPATH)
        append : bool = False
        if lastrun and forceAll == False:
            config.debug(datetime.datetime.strftime(lastrun, '%d/%m/%Y %H:%M'))
            lastrun -= datetime.timedelta(hours=0, minutes=15) #go a few minutes earlier to ensure nothing's missed
            config.info("Getting workflow data between now (%s) and %s" % (datetime.datetime.today().strftime('%d/%m/%Y %H:%M'), datetime.datetime.strftime(lastrun, '%d/%m/%Y %H:%M')))
            params = "&updated_after=" + datetime.datetime.strftime(lastrun, "%Y-%m-%dT%H:%M:%S.%fZ")
            wfReviewsXml = getWorkflows(params)
            append = True
        else: #if could not import, run for all
            config.warning("Could not import date last run.")
            config.info("Generating a tracker for all documents " + config.project().projectName())
            # Generate a tracker for ALL documents
            wfReviewsXml = getAllWorkflows()
            append = False

        if len(wfReviewsXml) == 0:
            config.warning("No new data found when searching for workflows.")
        else:
            addWorkflowData(wfReviewsXml)
            exportToExcel(FILEPATH, append)

def getAllWorkflows() -> list[Element]:
    return getWorkflows(params = "")

def getWorkflows(params : str) -> list[Element]:
    headers = {'Authorization': config.bearer()}
    url = config.projecturl() + "/workflows?page_size=100000" + params #can you believe it will let you do 100,000 page size, DOUBT - watch this break
    xml = getAPIResponse(url, headers, "getting workflow information") #initial call
    totalPages : int = int(ElTree.fromstring(xml.strip()).get('TotalPages'))
    numFound : int = int(ElTree.fromstring(xml.strip()).get('TotalResults'))

    wfReviewsXml = ElTree.fromstring(xml)

    currentPageNum = 1
    while currentPageNum < totalPages:
        url = config.projecturl() + "/workflows?page_size=100000&page_number=" + str(currentPageNum)
        xml = getAPIResponse(url, headers, "getting workflow information (page = %d)" % currentPageNum)
        wfReviewsXml.extend(ElTree.fromstring(xml))

        currentPageNum += 1

    wfReviewsXml = sorted(wfReviewsXml.findall('SearchResults/Workflow'), key=lambda step: step.find('DocumentNumber').text)
    config.debug(str(len(wfReviewsXml)))
    return wfReviewsXml

#Generate a tracker only on the selected documents
def genTrackerTextFile():
    #get the documents to search for using the input text file
    file = open(FOLDERPATH  + "\\docsList.txt", "r")
    textLines = [line.rstrip() for line in file]
    textLines = textLines[1::]  # remove top info line
    file.close()

    wfReviewsXml = getAllWorkflows()
    returnfields = "trackingid,docno,title,revision,author,reviewstatus,reviewSource"

    for iLine in textLines:
        #search up the user's doc number
        docXml = searchForDoc(config, "docno:" + iLine, returnfields)

        # if 0 search results
        if docXml == None:
            config.error("Error - Document could not be found in the register with the number %s" % iLine)
            continue

        docTitle = docXml.find('Title').text
        docRevision = docXml.find('Revision').text
        config.info("Document %s - %s (Current Rev = %s)" % (iLine, docTitle, docRevision))

        docTrackingID = docXml.find('TrackingId').text
        docWorkflowsXml = searchForWorkflow(wfReviewsXml, docTrackingID)
        addWorkflowData(docWorkflowsXml, docRevision)

    FILEPATH : str = FOLDERPATH + "\\Trackers\\" + config.project().projectCodePrefix() + "ExportedData.xlsx"
    exportToExcel(FILEPATH)