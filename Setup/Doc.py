import datetime
import webbrowser
from base64 import b64encode
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

import requests

from Setup.APIcommon import getPages, postAPIFile, et_findtagtext
from Setup.Directory import findMailingGroups, addUserIds
from Setup.FormField import AconexFormField, createxmltemplate
from Setup.Mail import openDraftLink


class DocFormField(AconexFormField):
    def __init__(self, label, fid, datatype, mandatorystr, value=None):
        mandatory: bool = False if mandatorystr in ["NOT_MANDATORY", "CONDITIONAL"] else True
        self.search_only : bool = False
        super().__init__(label, fid, datatype, mandatory, value)

    def setSearchable(self, searchfieldxml):
        if len(searchfieldxml) == 1:
            thissearchxml = searchfieldxml[0]
            self.searchfield = et_findtagtext(thissearchxml, "Identifier") #get the returnfield identifer name of this field

            #it is only a search return field if it has the SearchResultField tag and has a sortable attribute
            srfield = thissearchxml.find("Attributes/SearchResultField")
            if srfield is not None:
                sortable =  srfield.get("sortable")
                self.searchable(True)

            assert self.search_field() is not None

        elif len(searchfieldxml) == 0:
            self.searchfield = None
            self.searchable(False)

        else:
            raise ValueError("Multiple matching search fields found for a document field")


def searchForDoc(config, searchTerm : str, returnfields : str) -> Element | None:
    docxml = searchForDocs(config, searchTerm, returnfields)
    assert (len(docxml)<=1) #allow 0 or 1 results (sometimes there may be 0 if doc is no longer in use)
    if len(docxml) == 0:
        return None
    else:
        return docxml[0]


def searchForDocs(config, searchTerm: str, returnfields: str) -> list[Element] | None:
    parameters = {"search_type": "PAGED",  # PAGED, meaning return results by "pages" of variable size.
                  "return_fields": returnfields,
                  "search_query": searchTerm
                  }

    headers = {'Authorization': config.bearer()}
    baseurl = config.projecturl() + "/register"
    docxml = getPages(headers, parameters, baseurl, "searching for documents using term %s" % searchTerm)

    if len(docxml) == 0:
        config.logger.warning("No documents found using search term %s", searchTerm)

    return docxml


def getDocumentLink(config, trackingid):
    #docsearchlink = "{env}/hub/index.html?mainTarget=%2FSearchControlledDoc%3FSEARCH_ACTION%3D15%26tab%3D1%26searchMode%3D1%26searchQuery%3Did%3A{docid}".format(env=env, docid=docid)
    docsearchlink = "{env}/ViewDoc?trackingid={tid}&projectid={pid}&cversion=1&tab=0".format(env=config.env(), tid=trackingid, pid=config.project().projectID())
    webbrowser.open(docsearchlink)


def search_for_tracker(config, filepath : str, docnumber: str, dategen: str, silent : bool = True) -> bool | Element[str]:
    # check if tracker exists already
    config.logger.info("Searching for %s in doc register" % docnumber)

    #Get the searchable fields and return all of these
    returnfields = ",".join([df.search_field() for df in config.required_return_doc_fields()]) + ",trackingid" #we need to add tracking id because we need it for the link later
    docxml = searchForDoc(config, "docno:{}".format(docnumber), returnfields)

    url = config.projecturl() + "/register/"
    headers = {'Authorization': config.bearer(),
               'Content-Type': 'multipart/mixed',
               'boundary': 'myboundary'}

    if docxml == None:
        config.logger.error("Tracker not found in register. Please add a placeholder")
        return False

    else:
        config.logger.info("Tracker found in register.")

        docid, trackingid, xmldata = create_doc_xml(config, dategen, docxml, filepath)

        url += docid + "/supersede"
        response = requests.post(url, headers=headers, data=xmldata)

        if response.status_code != 200:
            config.error("There was an error superseding the tracker. %s" % response.reason)
            config.debug(response.text)
            return False

        config.logger.info("Tracker superseded")

        if not silent:
            getDocumentLink(config, trackingid)
            newdocid = et_findtagtext(ET.fromstring(response.text), "RegisterDocumentResult")
            registerTransmittal(config, newdocid)


def create_doc_xml(config, dategen: str, docxml: Element[str], filepath: str) -> tuple[
    str, str, str | None]:
    filename = filepath.split("\\")[-1]
    doctemplatexml = createxmltemplate('Document', config.mandatory_doc_fields())
    root = doctemplatexml.getroot()
    for elem in root:
        existingval = docxml.find(elem.tag)
        if existingval is not None:
            elem.text = existingval.text

    docid = docxml.attrib.pop('DocumentId')
    trackingid = docxml.find("TrackingId").text

    doctemplatexml.find('Revision').text = datetime.datetime.now().strftime("%Y/%m/%d")
    doctemplatexml.find('HasFile').text = "true"
    dn = doctemplatexml.find('DocumentNumber')
    root.remove(dn) #document number not required in the request

    # Type and Status is a required field but a list docs search only returns the name of the doc type, not the IDs
    doctypename = docxml.find('DocumentType').text
    doctypeid = config.docTypes()[doctypename]
    assert doctypeid is not None
    typeidxml = doctemplatexml.find('DocumentTypeId')
    typeidxml.text = doctypeid

    statusname = docxml.find('DocumentStatus').text
    docstatusid = config.docStatuses()[statusname]
    assert docstatusid is not None
    statusidxml = doctemplatexml.find('DocumentStatusId')
    statusidxml.text = docstatusid

    if config.searchForFormField('Milestone Date'):
        mdate = ET.Element('MilestoneDate')
        mdate.text = str(datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")) #"%Y-%m-%dT%H:%M:%S.%f"
        doctemplatexml.getroot().append(mdate)

    if not doctemplatexml.find('Comments'):
        commentsEl = ET.Element('Comments')

        doctemplatexml.getroot().append(commentsEl)

    doctemplatexml.find('Comments').text = "1 Design Information\n" + dategen
    xmldata = "--myboundary\n\n" + ET.tostring(root,
                                               encoding='unicode') + "\n--myboundary\n\nX-Filename: " + filename + "\n\n"

    with open(filepath, "rb") as f:  # read bytes of file
        encoded = b64encode(f.read())
        encStr = encoded.decode("utf-8")
        xmldata = xmldata + encStr + "\n\n--myboundary--"

    f.close()
    return docid, trackingid, xmldata

#TODO
def registerTransmittal(config, docid: str):
    headers = {'Authorization': config.bearer(),
               'Content-Type': 'multipart/mixed',
               'boundary': 'myboundary'}

    url = config.projecturl() + "/mail?is_draft=true"

    mailtemplatexml = createxmltemplate('Mail', config.mandatorymailfields())
    root = mailtemplatexml.getroot()

    transmittalmt = list(filter(lambda mt: mt.typename()=="Transmittal", config.mailtypes()))[0]

    root.find('MailTypeId').text = transmittalmt.corrtypeid()
    root.find('MailSubject').text = "Latest RFI Tracker"
    root.find('TotalAttachmentCount').text = "1"
    root.find('RichMailText').text = "true"

    mbody = ET.Element("MailBody")
    mbody.text = "."
    root.append(mbody)

    adid = ET.Element("AttachedDocId")
    adid.text = docid
    root.append(adid)

    #register it as coming from NM
    fromid = ET.Element('FromUserId')
    fromid.text = config.project().getMyUserID()
    root.append(fromid)

    #Set 'reason for issue' to issued for info
    reasonforissue = ET.Element('ReasonForIssue')
    reasonforissue.text = "4"
    root.append(reasonforissue)

    #Get the list of user IDS to send this transmittal to, based on people in the configured mailing groups
    mgroups : list [str] = config.project().getDistributeMGs()
    _, userIds = findMailingGroups(config, mgroups)
    touserid = root.find('ToUserId')
    root.remove(touserid)
    addUserIds(root,'ToUserId', userIds)

    ET.indent(root, space="", level=0)

    xmldata = ("--myboundary\nContent-Type: application/vnd.aconex.mail.v3+xml\n\n" +
               ET.tostring(root, encoding='unicode') + "\n--myboundary\n\nX-DocumentId: " + docid + "\n\n--myboundary--")

    response = requests.post(url, headers=headers, data=xmldata)

    if response.status_code != 200:
        config.error("There was an error transmitting the file. %s" % response.reason)
        print(response.text)
        exit()

    config.logger.info("Transmittal drafted")
    draftedMailId = ET.fromstring(response.text.strip()).find('NewMailId').text
    draftMailURL = config.env() + "/rsrc/20250422.1347/en_AU_DOC/mail/view/index.html#/" + config.project().projectID() + "/" + draftedMailId

    openDraftLink(config, response.text)
    #sendDraft(draftMailURL) TODO