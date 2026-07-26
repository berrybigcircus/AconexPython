import datetime
import webbrowser
from base64 import b64encode
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

import requests

from Setup.APIcommon import getPages, postAPIFile
from Setup.FormField import AconexFormField, createxmltemplate


class DocFormField(AconexFormField):
    def __init__(self, label, fid, datatype, mandatorystr, value=None):
        mandatory: bool = False if mandatorystr in ["NOT_MANDATORY", "CONDITIONAL"] else True
        super().__init__(label, fid, datatype, mandatory, value)

    def setSearchable(self, s : bool):
        self.__isSearchable = s

    def isSearchable(self) -> bool:
        if self.__isSearchable is None:
            pass #TODO
        return self.__isSearchable


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
    filename = filepath.split("\\")[-1]

    # check if tracker exists already
    config.logger.info("Searching for %s in doc register" % docnumber)
    #TODO - we need to get the mandatory doc fields for each project and add them programmatically to this list, not just keep guessing
    returnfields = "title,revision,author,statusid,doctype,discipline,category,vdrcode,selectlist1,trackingid,selectList2,selectlist3,comments"
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

        doctemplatexml = createxmltemplate('Document', config.mandatorydocfields())
        root = doctemplatexml.getroot()
        for elem in root:
            existingval = docxml.find(elem.tag)
            if existingval is not None:
                elem.text = existingval.text

        docid = docxml.attrib.pop('DocumentId')
        trackingid = docxml.find("TrackingId").text

        url += docid + "/supersede"

        doctemplatexml.find('Revision').text = datetime.datetime.now().strftime("%Y/%m/%d")
        doctemplatexml.find('HasFile').text = "true"
        dn = doctemplatexml.find('DocumentNumber')
        root.remove(dn)

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

        if config.searchForFormField('milestonedate'):
            mdate = ET.Element('milestonedate')
            mdate.text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
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

        response = requests.post(url, headers=headers, data=xmldata)

        if response.status_code != 200:
            config.error("There was an error superseding the tracker. %s" % response.reason)
            config.debug(response.text)
            return False

        config.logger.info("Tracker superseded")

        if not silent:
            getDocumentLink(config, trackingid)
        # registerTransmittal(newdocid)

