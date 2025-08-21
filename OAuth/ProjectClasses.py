import csv
import pickle

from OAuth.APIcommon import indexInput

class Project():
    def __init__(self, pname: str, pID: str, pCode: str = None):
        self.__projectname = pname
        self.__projectID = pID
        self.__projectCode = pCode

        self.__mailTypes = None

    def projectName(self) -> str:
        return self.__projectname

    def projectID(self) -> str:
        return self.__projectID

    def projectCodePrefix(self) -> str:
        if self.__projectCode:
            return self.__projectCode + " - "
        else:
            return ""

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

    #sometimes multiple orgs/people represent the 'client' for example, so it needs to be mapped together for 'ball in court'
    def getOrgMap(self) -> dict:
        match self.__projectCode:
            case "CDC":
                return {("Meera Mistry", "Arup"):"Client",
                        ("Mr Ben Bowley", "Leonard Design Architects"):"Client",
                        ("Mr Rob Wallace", "Meller Ltd."):"Client",
                        ("Ray Thain", "Nottingham University Hospital Trust"):"Client",
                        ("Mr Simon Oliver", "Nottingham University Hospital Trust"):"Client",
                        ("Ms Jo Dicken", "Arup"): "Client",
                        ("Ms Kate Yeomans", "Arup"): "Client",
                        ("Liz Chamberlain", "Leonard Design Architects"):"Architect",
                        ("Ms Robyn Lim", "Leonard Design Architects"):"Architect",
                        ("Mr Stuart McNash", "Arup"):"C&S Engineer",
                        ("Mrs Andria Ahmed", "Arup"):"Ignore",
                        ("Michael Wood", "Arup"):"C&S Engineer",
                        ("Mr Luke Webster", "Arup"):"C&S Engineer"
                }
            case _:
                return None

def projectSelection(debug: [] = []) -> Project:
    if len(debug) > 0:
        return Project(debug[0], debug[1], debug[2])

    ##Ask for project
    projectsList = {}
    try:
        csvfile = open("../getAllProjects/projectList.csv", "r", newline='')  # load stored projects
        reader = csv.reader(csvfile, delimiter=',')
        next(reader) #skip header row
        for row in reader:
            projectsList[row[0]] = [row[1], row[2]]
        csvfile.close()
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
