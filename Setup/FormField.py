from Setup.APIcommon import convertDateTimeStr
import xml.etree.ElementTree as ET  # for parsing xml

#Abstract
class AconexFormField:
    def __init__(self, label, fid, datatype, mandatory, value=None):
        self.__label : str = label
        self.__identifier : str = fid
        self.__datatype : str = datatype
        self.__value : str = value
        self.__isMandatory : bool = mandatory
        self.__isSearchable : bool = None
        self.selectionXML = None

    def label(self) -> str:
        return self.__label

    def identifier(self) -> str:
        return self.__identifier

    def datatype(self) -> str:
        return self.__datatype

    def isMandatory(self) -> bool:
        return self.__isMandatory

    # Abstract
    def isSearchable(self) -> bool:
        pass

    def setSelectionList(self, schemavals):
        self.selectionXML = schemavals
        self.__datatype = "LIST"

    def value(self) -> str:
        if not self.__value:
            return ""

        if self.__datatype == "BOOLEAN":
            return "Yes" if self.__value == "true" else "No"

        elif self.__datatype == "DATE":
            return convertDateTimeStr(self.__value, "%d/%m/%Y %H:%M:%S")

        else:
            return self.__value

    def setValue(self, val : str):
        self.__value = val

    def debug(self):
        print(self.__identifier)


#Create an xml empty template for creation of a new mail or document
def createxmltemplate(rootname : str, formfields : list[AconexFormField]):
    root = ET.Element(rootname)
    xmltree : ET.ElementTree = ET.ElementTree(root)

    #each of these need an xml element
    for formfield in formfields:
        elem = ET.Element(formfield.identifier())
        root.append(elem)

    return xmltree
