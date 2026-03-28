import webbrowser
from urllib.parse import urlencode
from xml.etree import ElementTree as ElTree
from xml.etree.ElementTree import Element

from Setup.APIcommon import getAPIResponse
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
    parameters = {"search_type": "PAGED",  # PAGED, meaning return results by "pages" of variable size.
                  "return_fields": returnfields,
                  "search_query": searchTerm
                  }

    headers = {'Authorization': config.bearer()}
    url = config.projecturl() + "/register?" + urlencode(parameters)

    xml = getAPIResponse(url, headers, "searching for document " + searchTerm)
    docXml = ElTree.fromstring(xml.strip()).find('SearchResults/') #there is only one doc returned so can use find rather than findall
    return docXml


def getDocumentLink(env, docid):
    docsearchlink = "{env}/hub/index.html?mainTarget=%2FSearchControlledDoc%3FSEARCH_ACTION%3D15%26tab%3D1%26searchMode%3D1%26searchQuery%3Did%3A{docid}".format(env=env, docid=docid)
    webbrowser.open(docsearchlink)
