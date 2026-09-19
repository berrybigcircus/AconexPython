from Setup.APIcommon import convertDateTimeStr, et_findtagtext
import xml.etree.ElementTree as ET  # for parsing xml

#Abstract
class AconexFormField:
    def __init__(self, label, fid, datatype, mandatory, value=None):
        self._label : str = label
        self.modifiedname : str = None
        self._identifier : str = fid
        self._datatype : str = datatype
        self._value : str = value
        self._isMandatory : bool = mandatory
        self.searchfield : str = None
        self._isSearchable : bool = False
        self.selectionList : AconexSchemaValues = None

    def label(self) -> str:
        return self._label

    def identifier(self) -> str:
        return self._identifier

    def datatype(self) -> str:
        return self._datatype

    def isMandatory(self) -> bool:
        return self._isMandatory

    def search_field(self) -> str | None:
        return self.searchfield

    def searchable(self, s : bool):
        self._isSearchable = s

    def isSearchable(self) -> bool:
        return self._isSearchable

    def setSelectionList(self, schemavals):
        self.selectionList = AconexSchemaValues(schemavals)
        if self.selectionList.hasIDs():
            self._datatype = "LIST_WITH_CODES"
        else:
            self._datatype = "LIST"


    def value(self) -> str:
        if not self._value:
            return ""

        if self._datatype == "BOOLEAN":
            return "Yes" if self._value == "true" else "No"

        elif self._datatype == "DATE":
            return convertDateTimeStr(self._value, "%d/%m/%Y %H:%M:%S")

        else:
            return self._value

    def setValue(self, val : str):
        self._value = val

    def debug(self):
        print("%s %s %s Mandatory=%s Searchable=%s" % (self.label(), self.identifier(), self.datatype(), self.isMandatory(), self.isSearchable()))

class AconexSchemaValues():
    def __init__(self, schemavals ):
        self.SchemaVals : list[AconexSchemaValue] = []
        for schemaval in schemavals:
            value = et_findtagtext(schemaval, "Value")
            id = et_findtagtext(schemaval, "Id", check_exists=True)
            self.SchemaVals.append(AconexSchemaValue(value, id))

    #if the selection list is in the format ID: Value
    def hasIDs(self):
        return all(schemaval.schemaid for schemaval in self.SchemaVals)

    def dict_form(self) -> dict:
        if self.hasIDs():
            return {
                sv.value : sv.schemaid for sv in self.SchemaVals
            }
        else:
            return {}

class AconexSchemaValue:
    def __init__(self, value : str, id : str = None):
        self.value = value
        self.schemaid = id if id else None

#Create an xml empty template for creation of a new mail or document
def createxmltemplate(rootname : str, formfields : list[AconexFormField]):
    root = ET.Element(rootname)
    xmltree : ET.ElementTree = ET.ElementTree(root)

    #each of these need an xml element
    for formfield in formfields:
        elem = ET.Element(formfield.identifier())
        root.append(elem)

    return xmltree
