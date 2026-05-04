import csv
import pathlib

from Setup.APIcommon import indexInput

class Project():
    def __init__(self, pname: str, pID: str, pCode: str = None):
        self.__projectname = pname
        self.__projectID = pID
        self.__projectCode = pCode

        self.__mailTypes = None

        self.folderroot = str(pathlib.Path(__file__).parents[1].resolve())

    def projectName(self) -> str:
        # sanitise MTP project name
        if self.projectCode() == "MTP":
            return "MTP"
        return self.__projectname

    def projectID(self) -> str:
        return self.__projectID

    def projectCodePrefix(self) -> str:
        if self.__projectCode:
            return self.__projectCode + " - "
        else:
            return ""

    def projectCode(self) -> str:
        return self.__projectCode

    #list the RFI mail types that are valid for this project, that can start a RFI thread
    def getRFISetup(self ) -> (str, list[str]):
        match self.__projectCode:
            case "HBT":
                return "RFI Description", ["Request For Information", "Tender RFI"]  #for EA1 testing
            case "LEU":
                return "RFI Description", ["Contractor RFI"]
            case "A5057":
                return "Description", ["Sub-Contractor RFI", "Client RFI", "Request For Information"]
            case _: #else
                return "RFI Description", ["Sub-Contractor RFI", "Request For Information",  "Client RFI"]

    def getRFIReplySetup(self) -> (str, list[str]):
        match self.__projectCode:
            case "HBT":
                return "RFI Response", ["RFI Response"]
            case "LEU":
                return "RFI Response", ["Response to Contractor RFI"]
            case "A5057" | "MTP":
                return "RFI Response", ["Response to Client RFI", "Response to RFI", "Response to Sub-Contractor RFI"]
            case _:
                return "RFI Response", ["Response to RFI", "Response to Sub-Contractor RFI"]

    #this is the name of the mail field that tracks who the rfi goes to. it is needed to know who the action is with in the tracker
    def getRFIDiscSetup(self) -> str:
        if self.__projectCode in ["TEST", "LEU"]:
            return "Action With"
        else: #luckily i always call it discipline nowadays
            return "Discipline"

    #The project naming might determine which doc number it needs to be under
    def getRFIDocNumber(self) -> str:
        if self.__projectCode == "JFW":
            return "{}-HBC-XX-XX-L-W-79904".format(self.__projectCode)
        elif self.__projectCode == "9910":
            return "CNJC_9910-HBC-NJC-XX-L-W-9904"
        elif self.__projectCode == "9961":
            return "CTJC_9661-HBC-TJC-XX-L-W-9904"
        elif self.__projectCode == "9907":
            return "CLCC_9907-HBC-LCC-XX-L-W-9904"
        elif self.__projectCode == "51023":
            return "CMCC_51023-HBC-MCC-XX-L-W-9904"
        else:
            return "{}-HBC-XX-XX-L-X-9904".format(self.__projectCode)

    #return the HB org id for UK1 or EA1 (pre-saved rather than from a get request)
    def getMyOrgID(self) -> str:
        if self.__projectID == "1879048648":
            return "1879048779"
        else:
            return "268481852"

    def getMyUserID(self) -> str:
        if self.__projectID == "1879048648": #EA
            return "1879050797"
        else:
            return "269118732"

    def getEWNSetup(self) -> str:
        match self.__projectCode:
            case "HBT":
                return (["(ECC) Early Warning Notice"],["Response to EWN"])
            case _:
                return (["Early Warning Notice"], ["Response to Early Warning Notice"])


    #this is which mailing groups to auto-transmit the trackers to
    def getDistributeMGs(self):
        match self.__projectCode:
            case "HBT":
                return ["Fabulous Architects", "Creative Spaces", "All"]
            case "MTP":
                return ["CPMG (Architect)", "Fairhursts (Client Arch Consultant)", "Client Team", "Hexa Consulting (Structural engineer)",
                        "Waterman (MEP Client Consultant)", "Waterman Structures (Client Struct Consultant)", "William Bailey WB (Mechanical)"]
            case _:
                return ["Int design team"]

    def getRFITrackerLocation(self) -> str:
        return "{}\\d_Mail\\RFIs\\Trackers\\{}Exported Data.xlsx".format(self.folderroot, self.projectCodePrefix())

    def getMailTemplateLocation(self) -> str:
        return "{}\\d_Mail\\Import\\{}Mail_Template.xlsx".format(self.folderroot, self.projectCodePrefix())

    def getProjectDirectoryLocation(self) -> str:
        return "{}\\a_NewUser\\PDirectories\\{}Project Directory.xlsx".format(self.folderroot, self.projectCodePrefix())

    def getPickleLocation(self) -> str:
        return "{}\\d_Mail\\RFIs\\Pickle\\{}mails.pkl".format(self.folderroot, self.projectCodePrefix())

def projectSelection(debug: [] = []) -> Project:
    if len(debug) > 0:
        return Project(debug[0], debug[1], debug[2])

    ##Ask for project
    projectsList : dict[str, list] = getProjectsList()

    print("CURRENT PROJECTS:")
    for i, pID in enumerate(projectsList.keys()):  # print projects to user
        print("    %d - %s %s (%s)" % (i, projectsList[pID][1], projectsList[pID][0], pID))

    confirm = "n"
    projectname : str
    chosenProjectID : str

    projectCodes : list[str]
    _, projectCodes = zip(*projectsList.values())

    while confirm.upper() != "Y" and confirm.lower() != "yes":
        projectIndex = indexInput(len(projectsList) - 1, list(map(str.casefold, projectCodes)))

        if isinstance(projectIndex, str): #if one of allowed project code
            projectcode = projectIndex.upper()
            projectIndex = projectCodes.index(projectcode)

        chosenProjectID = list(projectsList.keys())[projectIndex]
        projDetails = list(projectsList.values())[projectIndex]
        projectname, projectcode = projDetails

        print("Project - %s" % projectname)

        confirm = input("Confirm (Y/N):")

    return Project(projectname, chosenProjectID, projectcode)


def getProjectsList(logger = None) -> dict[str, list]:
    projectsList = {}
    FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
    try:
        csvfile = open(FOLDERPATH + "\\getAllProjects\\projectList.csv", "r", newline='')  # load stored projects
        reader = csv.reader(csvfile, delimiter=',')
        next(reader)  # skip header row
        for row in reader:
            projectsList[row[0]] = [row[1], row[2]]
        csvfile.close()
    except IOError:
        raise IOError("Error loading project list.")

    return projectsList