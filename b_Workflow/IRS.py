## Work for CDC overall tracker showing
# Workflows (reviews)
# Documents not reviewed
import pickle

from Setup.APIcommon import et_findtagtext, cleanOrgName
from Setup.Doc import searchForDocs
from Setup.config import config
from b_Workflow.WorkflowComments import COLUMN_MAP, wf_get_doc_num, exportToExcel, getAllWorkflows, addWorkflowData


def main():
    #generate workflow tracker
    #add these columns for CDC
    custom_columns : dict = {
    "Tracking ID": [],
    "To be revised?": [],
    "Assigned to Name": [],
    "File type": [],
    "Document Status": [],
    "Document Type": []
    }

    wf_reviews_xml = getAllWorkflows()
    workflow_data = addWorkflowData(wf_reviews_xml, custom_columns, CDC_IRS_filter)

    #Use HBDC All Docs to get all docs first
    HBDCALLDOCS = "matchAll:1 confidential:0 AND NOT (SharedWith_singleSelect:Internal* OR SharedWith_singleSelect:Shared*)"  # manual recreation of this search
    returnfields = "trackingid,docno,title,revision,author,statusid,reviewstatus,reviewSource,vdrcode,asBuiltRequired,doctype,fileType"
    docsxml = searchForDocs(config, HBDCALLDOCS, returnfields, "False")

    workflow_docs = dict(zip(workflow_data["Tracking ID"], workflow_data["Latest revision?"]))

    docsxml_final = []
    for docxml in docsxml:
        tid = et_findtagtext(docxml, "TrackingId", True)
        if not workflow_docs.get(tid, False): #if latest_rev is false, keep the doc. If doc was not in workflow_data, keep
            docsxml_final.append(docxml)

    workflow_data = add_to_data(workflow_data, docsxml_final)
    assert len(workflow_data["Document Number"]) == len(workflow_data["Comments"])
    exportToExcel(config.project().getWFExportDataLocation(), workflow_data)

#custom filter
def CDC_IRS_filter(ctx):
    assigned = {name.strip() for name in ctx["assignedtoname"].split(", ")}
    return (
            ctx["stepstatus"] == "Forecast" or
            ctx["Status"] == "No Longer In Use" or
            assigned.intersection({"Luke Webster", "Michael Wood"}) or
            (ctx["wfstatus"] == "Terminated" and "Henry Brothers" in ctx["assignedtoorg"])
    )

#take search_doc xml and add to workflow_data dict
def add_to_data(workflow_data, docsxml):

    for docxml in docsxml:
        context = {
            "docnum": wf_get_doc_num(docxml, None),
            "title": et_findtagtext(docxml, "Title", is_optional=False),
            "revision": et_findtagtext(docxml, "Revision", is_optional=False),
            "createdby": cleanOrgName(et_findtagtext(docxml, "Author", is_optional=False)),
            "Status": et_findtagtext(docxml, "DocumentStatus", is_optional=False),
            "reviewstatus": "",
            "trackingid": et_findtagtext(docxml, 'TrackingId', is_optional=False),
            "wfnumber" : "",
            "wfstatus": "",
            "datein": "",
            "stepname": "",
            "assignedtoorg": "",
            "stepstatus": "",
            "stepoutcome": "",
            "datecompleted": "",
            "comments": "",
            "latestrev": True,
            "markedup": False,
            "AsBuiltRequired": et_findtagtext(docxml, 'AsBuiltRequired', is_optional=False),
            "assignedtoname": "",
            "Type": et_findtagtext(docxml, 'DocumentType', is_optional=False),
            "FileType": et_findtagtext(docxml, "FileType", is_optional=False)
            }

        assert context["docnum"] is not None

        for export_name in workflow_data:
            workflow_data[export_name].append(
                context[COLUMN_MAP[export_name]]
            )

    return workflow_data