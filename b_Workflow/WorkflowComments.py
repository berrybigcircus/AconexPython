import copy
import datetime
import os
import xml.etree.ElementTree as ElTree  # for parsing xml
from typing import Any
from xml.etree.ElementTree import Element

import pandas  # for exporting to excel

from Setup.config import config, refreshTracker, get_modification_time
from Setup.Doc import searchForDoc, search_for_tracker, DocFormField

from Setup.APIcommon import getAPIResponse, convertDateTimeStr, cleanOrgName, importLastRun, et_findtagtext

import pickle

DEFAULT_WORKFLOW_COLUMNS : dict[str, list[str | bool]] = {
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
    "Marked up file?": []
}


def searchForWorkflow(wfReviewsXml, trackingId) -> list[Any]:
    #find the document's workflow reviews, using the tracking id
    wfReviewsXml = [wfxml for wfxml in wfReviewsXml if wfxml.find('DocumentTrackingId').text == trackingId]

    wfReviewsXml = sorted(wfReviewsXml, key=lambda step: (step.find('DateIn').text is None, step.find('DateIn').text)) #ensure comments are sorted by date (earliest to latest)
    return wfReviewsXml

def wf_get_doc_num(docxml, reviewxml) -> str:
    return docxml.find('DocumentNumber').text if docxml is not None else reviewxml.find('DocumentNumber').text

def wf_get_assigned_orgs(reviewxml) -> str:
    assigneesOrgsXML = reviewxml.findall('Assignees/Assignee/OrganizationName')
    return "\n".join(set([cleanOrgName(orgxml.text) for orgxml in assigneesOrgsXML]))

def wf_get_assigned_names(reviewxml) -> str:
    assigneesNamesXML = reviewxml.findall('Assignees/Assignee/Name')
    return "\n".join(set([namexml.text for namexml in assigneesNamesXML]))


def wf_get_step_outcome(reviewxml, stepstatus) -> str:
    stepoutcome = et_findtagtext(reviewxml, 'StepOutcome', is_optional=False)
    # This happens when C-Rejected ends workflows early - the outcome for the other steps is stuck as pending
    if stepoutcome in ["Pending", "Under Review"] and stepstatus == "Completed":
        stepoutcome = "None"

    return stepoutcome

def wf_get_if_latest_rev(docxml, wf_rev) -> bool:
    if not docxml:
        return False
    current_rev = et_findtagtext(docxml, 'Revision', is_optional=False)
    return wf_rev == current_rev

def wf_get_if_markedup_file(docxml, reviewxml) -> bool:
    if not docxml:
        return False

    OGfilename = et_findtagtext(reviewxml, "FileName", is_optional=True)
    OGfilesize = et_findtagtext(reviewxml, "FileSize", is_optional=True)

    currentfilename = et_findtagtext(docxml, "Filename", is_optional=True)
    currentfilesize = et_findtagtext(docxml, "FileSize", is_optional=True)

    return OGfilename != currentfilename or OGfilesize != currentfilesize

def wf_get_formfield_val(formfield_name : str) -> str:

    pass

def wf_filter(ctx):
    return (
            ctx["stepstatus"] in ["Forecast", "Terminated"]
            or ctx["wfstatus"] == "Terminated"
            or ctx["stepoutcome"] == "None"
            or ctx["Status"] == "No Longer In Use"
    )

COLUMN_MAP = {
    "Document Number": "docnum",
    "Title": "title",
    "Revision": "revision",
    "Created by": "createdby",
    "Workflow Number": "wfnumber",
    "Workflow Status": "wfstatus",
    "Date In": "datein",
    "Step Name": "stepname",
    "Assigned to Org": "assignedtoorg",
    "Step Outcome": "stepoutcome",
    "Date of Comments": "datecompleted",
    "Comments": "comments",
    "Workflow Outcome": "reviewstatus",
    "Latest revision?": "latestrev",
    "Marked up file?": "markedup",
    "To be revised?": "AsBuiltRequired",
    "Tracking ID": "trackingid",
    "Assigned to Name": "assignedtoname",
    "File type": "FileType",
    "Document Status": "Status",
    "Document Type": "Type"
}

def get_custom_formfields(fieldnames : list[str]) -> list[DocFormField]:
    form_fields : list[str] = []

    for fieldname in fieldnames:
        ff = config.searchForFormField(fieldname)
        if ff:
            form_fields.append(ff)

    return form_fields

def addWorkflowData(wf_reviews_xml, custom_columns = None, workflow_filter=wf_filter) -> dict:
    prevID = None
    skipcount = 0
    returnfields = "trackingid,docno,title,revision,author,reviewstatus,reviewSource,statusid,filename,fileSize,fileType,doctype"
    metadata_call = False

    custom_formfields = []
    if custom_columns:
        custom_formfields = [ff for fieldname in list(custom_columns.keys()) if (ff := config.searchForFormField(COLUMN_MAP[fieldname]))]
        search_names = [ff.search_field() for ff in custom_formfields if ff.search_field()]
        metadata_call = any(not ff.search_field() for ff in custom_formfields)
        if search_names:
            returnfields += ",{}".format(",".join(search_names))


    docxml : Element | None = None
    doc_context : dict = {}

    workflow_data = copy.deepcopy(DEFAULT_WORKFLOW_COLUMNS) #get a copy of the default dict but dont overwrite
    if custom_columns:
        workflow_data.update(copy.deepcopy(custom_columns))

    assert len(workflow_data["Document Number"]) == 0

    for reviewxml in wf_reviews_xml:  # in case it's been in multiple reviews
        docTrackingID = et_findtagtext(reviewxml, 'DocumentTrackingId')
        wf_rev = et_findtagtext(reviewxml, "DocumentRevision", is_optional=False)

        # we need to run this every time because we need to know the doc's current doc number, not what it was in the WF - this is in case the number changes
        if prevID is None or docTrackingID != prevID:
            docxml = searchForDoc(config, "trackingid:" + docTrackingID, returnfields)
            if docxml is not None:
                doc_context = {
                    "Status": et_findtagtext(docxml, "DocumentStatus", is_optional=False),
                    "docnum": wf_get_doc_num(docxml, reviewxml),
                    "createdby": cleanOrgName(et_findtagtext(docxml, "Author", is_optional=False)),
                    "reviewstatus": et_findtagtext(docxml, "ReviewStatus", is_optional=False),
                    "Type": et_findtagtext(docxml, "DocumentType", is_optional=False),
                    "FileType": et_findtagtext(docxml, "FileType", is_optional=False)
                }
                if custom_formfields:
                    if metadata_call:
                        #make get doc metadata call for other field values
                        pass

                    for ff in custom_formfields:
                        if ff.identifier == "trackingid":
                            continue
                        doc_context[ff.identifier()] = et_findtagtext(docxml, ff.identifier(), is_optional=True)

            else:
                doc_context = {
                    "Status" : "No Longer In Use"
                }

        stepstatus = et_findtagtext(reviewxml, "StepStatus", is_optional=False)
        wfstatus = et_findtagtext(reviewxml, "WorkflowStatus", is_optional=False)

        context = {
            **doc_context,
            #reviewxml data
            "title": et_findtagtext(reviewxml, "DocumentTitle", is_optional=False),
            "revision": wf_rev,
            "trackingid": docTrackingID,
            "wfnumber": et_findtagtext(reviewxml, "WorkflowNumber", is_optional=False),
            "wfstatus": wfstatus,
            "datein": convertDateTimeStr(et_findtagtext(reviewxml, "DateIn", is_optional=False),"%d/%m/%Y %H:%M:%S"),
            "stepname": et_findtagtext(reviewxml, "StepName", is_optional=False),
            "assignedtoorg": wf_get_assigned_orgs(reviewxml),
            "stepstatus": stepstatus,
            "stepoutcome": wf_get_step_outcome(reviewxml, stepstatus),
            "datecompleted": convertDateTimeStr(et_findtagtext(reviewxml, "DateCompleted", is_optional=False),"%d/%m/%Y %H:%M:%S"),
            "comments": et_findtagtext(reviewxml, "Comments", is_optional=True),
            "latestrev": wf_get_if_latest_rev(docxml, wf_rev),
            "markedup": wf_get_if_markedup_file(docxml, reviewxml),
            "assignedtoname": wf_get_assigned_names(reviewxml)
        }

        if workflow_filter(context):
            prevID = docTrackingID
            skipcount +=1
            continue

        for export_name in workflow_data:
            workflow_data[export_name].append(
                context[COLUMN_MAP[export_name]]
            )

        prevID = docTrackingID

    config.info("Skipped %d" % skipcount)
    config.debug(str(len(workflow_data["Document Number"])))
    return workflow_data

def exportToExcel(fname: str, workflow_data : dict):
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
    dataframe = pandas.DataFrame(data=workflow_data)  # convert into pandas data frame for exporting
    dataframe.drop_duplicates() #remove any duplicates which might have appeared when appending new data to existing
    dataframe.to_excel(writer,
           sheet_name="RawData",
           header= True,
           startrow = 0,
           index=False) #no index col

    writer.close()
    config.info("     Workflow data added to ExportedData.xlsx")

def main(inputUseTextFile : str, forceAll : bool = True):
    FILEPATH : str = config.project().getWFExportDataLocation()

    workflow_data : dict = {}

    if inputUseTextFile == "y":
        genTrackerTextFile()
    else:
        #Import the date the tracker was last ran
        lastrun : datetime.datetime = importLastRun(FILEPATH)
        pickle_path = config.project().getWFPickleLocation()
        config.logger.info(
            f"Pickle={pickle_path}"
        )
        if lastrun and forceAll == False:
            lastrun -= datetime.timedelta(hours=0, minutes=15) #go a few minutes earlier to ensure nothing's missed

            try:
                with open(pickle_path, "rb") as f:
                    workflow_data.update(pickle.load(f))
                f.close()
                config.logger.info("Loaded workflow data pickle")

                config.info("Getting workflow data between now (%s) and %s" % (datetime.datetime.today().strftime('%d/%m/%Y %H:%M'), datetime.datetime.strftime(lastrun, '%d/%m/%Y %H:%M')))
                params = "&updated_after=" + datetime.datetime.strftime(lastrun, "%Y-%m-%dT%H:%M:%S.%fZ")
                wfNewXML = getWorkflows(params)

            except:
                forceAll = True

        if forceAll or not lastrun: #if could not import, run for all
            config.info("Generating a tracker for all documents in " + config.project().projectName())
            # Generate a tracker for ALL documents
            wfNewXML = getAllWorkflows()

        if len(wfNewXML) == 0:
            config.warning("No new data found when searching for workflows.")
            return

        else:
            config.logger.info(
                f"Project: {config.project().projectName()}"
            )

            config.logger.info(
                f"Pickle: {pickle_path }"
            )
            workflow_data = addWorkflowData(wfNewXML, DEFAULT_WORKFLOW_COLUMNS)
            with open(pickle_path, "wb") as f:
                pickle.dump(workflow_data, f)
                config.logger.info("Workflow Data dictionary dumped to pickle file")

            f.close()

            exportToExcel(FILEPATH, workflow_data)

            wfpath = FILEPATH.replace("ExportedData.xlsx",
                                           "Workflow Tracker.xlsx")  # get the finalised tracker not the raw export

            return uploadWFTracker(config, wfpath)


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
    path = config.project().folderroot + "\\b_Workflow\\docsList.txt"
    file = open(path, "r")
    textLines = [line.rstrip() for line in file]
    textLines = textLines[1::]  # remove top info line
    file.close()

    wfReviewsXml = getAllWorkflows()
    returnfields = "trackingid,docno,title,revision,author,reviewstatus,reviewSource,vdrcode"

    workflow_data : dict = DEFAULT_WORKFLOW_COLUMNS

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
        workflow_data = addWorkflowData(docWorkflowsXml, workflow_data, docRevision)

    exportToExcel(config.project().getWFExportDataLocation(), workflow_data)

def uploadWFTracker(config, filepath, force_upload : bool = False):
    if not force_upload:
        dategen = refreshTracker(filepath)
    else:
        dategen = get_modification_time(filepath)

    if force_upload or dategen:
        docnumber = config.project().getWFTrackerNumber()
        return search_for_tracker(config, filepath, docnumber, dategen)

    else:
        config.logger.warning("Tracker at %s not uploaded." % filepath)
        return False, None