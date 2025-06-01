import pickle
from xml.etree import ElementTree as ET

from OAuth.APIcommon import getAPIResponse, indexInput
from OAuth.MailClasses import AconexMailType


class Project():
    def __init__(self, pname: str, pID: str, pCode: str = None):
        self.__projectname = pname
        self.__projectID = pID
        self.__projectCode = pCode

        self.__mailTypes : [AconexMailType] = None

    def projectName(self) -> str:
        return self.__projectname

    def projectID(self) -> str:
        return self.__projectID

    def projectCodePrefix(self) -> str:
        if self.__projectCode:
            return self.__projectCode + " - "
        else:
            return ""

    def getMailSchema(self, PROJECTURL, bearer) -> list[AconexMailType]:
        headers = {'Authorization': bearer,
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}
        url = PROJECTURL + "/mail/schema/creation"

        xml = getAPIResponse(url=url, headers=headers, explanation="getting the mail creation schema for the project.")
        return self.getMailTypes(ET.fromstring(xml.strip()))

    def getMailTypes(self, mailSchemaXML) -> [AconexMailType]:
        mailTypesXML = mailSchemaXML.find(
            "./MultiValueSchemaField/./[Identifier='MailTypeId']")  # find the field for mail types

        mailTypesXML = mailTypesXML.findall("SchemaValues/SchemaValue")
        mailTypes: list[AconexMailType] = []

        for elem in mailTypesXML:
            typeName = elem.find('Value').text

            m = AconexMailType(typeID=elem.find('Id').text, typeName=typeName)
            ffLink = elem.find(
                'Links/Link')  # link to api request that will give you the details for the form fields for that mail type
            if ffLink is not None:
                m.getFormFields(ffLink.get('href'))
            mailTypes.append(m)

        self.__mailTypes = mailTypes
        return self.__mailTypes

    def getProjectInviteMailID(self) -> str:
        #Advice mail type is for HB Test
        projectInviteMail = list(filter(lambda mt : mt.typename() in ["Project Invitation","Advice"], self.__mailTypes))
        return projectInviteMail[0].corrtypeid()

    #list the RFI mail types that are valid for this project, that can start a RFI thread
    def getRFISetup(self ) -> (str, list[str]):
        match self.__projectCode:
            case "TEST":
                return "RFI Description", ["Request For Information", "Tender RFI"]  #for EA1 testing
            case "LEU":
                return "RFI Description", ["Contractor RFI"]
            case "A5057":
                return "Description", ["Sub-Contractor RFI", "Client RFI", "Request For Information"]
            case _: #else
                return "RFI Description", ["Sub-Contractor RFI", "Request For Information"]

    def getRFIReplySetup(self) -> (str, list[str]):
        match self.__projectCode:
            case "TEST":
                return "RFI Response", ["RFI Response"]
            case "LEU":
                return "RFI Response", ["Response to Contractor RFI"]
            case "A5057":
                return "RFI Response", ["Response to Client RFI", "Response to RFI", "Response to Sub-Contractor RFI"]
            case _:
                return "RFI Response", ["Response to RFI", "Response to Sub-Contractor RFI"]

    #this is the name of the mail field that tracks who the rfi goes to. it is needed to know who the action is with in the tracker
    def getRFIDiscSetup(self) -> str:
        if self.__projectCode in ["TEST", "LEU"]:
            return "Action With"
        else: #luckily i always call it discipline nowadays
            return "Discipline"


def projectSelection(debug: bool = False) -> Project:
    if debug:
        return Project("HB Test", "1879048648", "TEST")

    ##Ask for project
    try:
        fp = open("../getAllProjects/projectList.txt", "rb")  # load stored projects
        projectsList = pickle.load(fp)  # load as project dictionary
        fp.close()
    except IOError:
        print("Error loading project list.")
        exit()

    print("CURRENT PROJECTS:")
    for i, pID in enumerate(projectsList.keys()):  # print projects to user
        print("    %d - %s %s (%s)" % (i, projectsList[pID][1], projectsList[pID][0], pID))

    confirm = "n"
    projectname : str
    chosenProjectID : str

    while confirm.upper() != "Y" and confirm.lower() != "yes":
        projectIndex = indexInput(len(projectsList) - 1)
        chosenProjectID = list(projectsList.keys())[projectIndex]
        projDetails = list(projectsList.values())[projectIndex]
        projectname, projectcode = projDetails

        print(projectcode)

        print("Project - %s" % projectname)

        confirm = input("Confirm (Y/N):")

    return Project(projectname, chosenProjectID, projectcode)
