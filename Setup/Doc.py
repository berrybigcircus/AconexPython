import webbrowser
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

from Setup.APIcommon import getPages
from Setup.FormField import AconexFormField


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


def getDocumentLink(env, docid):
    docsearchlink = "{env}/hub/index.html?mainTarget=%2FSearchControlledDoc%3FSEARCH_ACTION%3D15%26tab%3D1%26searchMode%3D1%26searchQuery%3Did%3A{docid}".format(env=env, docid=docid)
    webbrowser.open(docsearchlink)
