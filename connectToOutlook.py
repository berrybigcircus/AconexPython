import pathlib
from datetime import datetime
from typing import Any

import win32com.client
import re

from Setup import EAsetup, UK1setup
from Setup.Project import getProjectsList
from Setup.config import init, config
from Setup.getAllProjects import getAllProjects
from b_Workflow import WorkflowComments
from d_Mail.RFIs import RFITracker
from f_AutoMail.EW import EWExcel

FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
DEBUG = False #TODO - FOR EA OR UK1

class OutlookConfig:
    def __init__(self, debug = False):
        self.bearer = EAsetup.bearer if debug else UK1setup.bearer
        self.env = EAsetup.env if debug else UK1setup.env

    def initWrapper(self, debug=None):
        init(self.bearer, self.env, debug)


outlookconfig : OutlookConfig = OutlookConfig(debug=False)

def main():
    outlook = connect()

    aconexfolder = find_folder("Aconex", outlook)

    aconexmessages = aconexfolder.items
    aconexmessages.Sort("[ReceivedTime]", True) #ensure sorted by date received

    lastRan: str = getLastRan()
    latestmessages = aconexmessages.Restrict("[ReceivedTime] >= '" + lastRan + "'")
    latestmessages = latestmessages.Restrict("Not([Categories] = 'Python Parsed')")
    config.debug(f"{latestmessages.Count=}")
    latestmessages.Sort("[ReceivedTime]", False) #start with the oldest

    runset : set[tuple] = set()
    success : bool = True
    for item in latestmessages:
        temp = checkEmail(item, runset)
        runset.add(temp[0])
        success = success and temp[1]

    if success:
        lastRan = datetime.now()
        with open(FOLDERPATH + "\\Setup\\outlookLastRan.txt", "w") as file:
            file.write(lastRan.strftime('%d/%m/%Y %H:%M %p'))
            file.close()


def find_folder(folder_to_find: str, outlook) -> object:
    o_folder: object = None
    # get my account, find Aconex folder
    for i in range(1, outlook.Folders.Count + 1):
        root = outlook.folders.Item(i)
        if root.Name == "nicole.millinship@henrybrothers.co.uk":
            o_folder = root.Folders[folder_to_find]

    if not o_folder:
        raise Exception("No '%s' outlook folder found" % folder_to_find)
    return o_folder


def connect() -> Any:
    # connect to open outlook application - must be open on the machine for this to work
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNameSpace('MAPI')
    except AttributeError:
        raise AttributeError("Could not run. Outlook is not open.")
    return outlook


def getLastRan() -> str:
    with open(FOLDERPATH + "\\Setup\\outlookLastRan.txt", "r") as file:
        strDateLastRan = file.read()
        file.close()

    return strDateLastRan

def checkEmail(item : object, runset : set[tuple]) -> list[tuple|bool|None]:
    subject : str = item.Subject
    #Get mail type from subject line, removing organisation and sequence num
    reg = "[a-zA-Z0-9 "+ re.escape(".'+") + "]+-([a-zA-Z" + re.escape("-") + "]+)-[0-9]+:"
    result = re.search(reg, subject)
    if not result:
        config.error("Cannot parse mail type from subject %s. Check the mail number is valid for the regex" % subject)
        item.Categories = 'Python Parsed'
        item.Save()
        return [None, False]

    mailTypeCode : str = result.group(1)
    config.debug(f"{subject=}")
    config.debug(f"{mailTypeCode=}")

    #get projectname from mail body, by searching for the headings "Project" and "Type"
    mbody : str = item.body
    start = "Project:"
    end = "\nType:"
    reg = start + "(.*?)" + end
    result = re.search(reg, mbody[0:len(mbody)//2]) #split body in half as it will definitely be in first half
    if not result:
        config.error("Cannot parse projectname from email body")
        return [None, True]

    projectname : str = result.group(1).strip()

    #Check if we have already just ran the script and do not need to run again
    if (projectname, mailTypeCode) in runset:
        config.info("Code just ran. Skipping...")
        item.Categories = 'Python Parsed'
        item.Save()
        return [None, True]

    runagain = True
    success = True

    #WORKFLOWS
    if mailTypeCode == "WTRAN":
        config.debug("Running wfComments for projectname %s" % projectname)
        success = autorunWFComments(projectname)
        runagain = False #do not need to run this more than once at a time

    elif mailTypeCode == "RFI" or mailTypeCode == "SUBRFI" or mailTypeCode == "RTSCRFI" or mailTypeCode == "RTRFI":
        config.debug("Running rfiTracker for projectname %s" % projectname)
        success = autorunRFITracker(projectname)
        runagain = False

    #EARLY WARNINGS
    elif mailTypeCode == "EWN" or mailTypeCode == "EC-EWN":
        if projectname in ["Wolverhampton Police", "Stechford Police", "HB Test"]:
            config.debug("Running sendEWExcel for projectname %s" % projectname)
            mailno = getmailno(subject)
            config.debug(f"{mailno=}")
            success = sendEWExcel(projectname, mailno)
        runagain = True

    #If code ran successfully, ignore this email in future
    if success:
        item.Categories = 'Python Parsed'
        item.Save()
        config.info("Categorised mail.")

    if not runagain:
        return [(projectname, mailTypeCode), success]

    return [None, success]

#mail no is at start of subject line, followed by :
def getmailno(subject : str) -> str:
    splsub = subject.split(":")
    if len(splsub) < 2:
        raise Exception("Cannot parse mail type from subject.")

    return splsub[0]

def sendEWExcel(projectname: str, mailno: str) -> bool:
    initProject(outlookconfig, projectname, "projectnames")
    EWExcel.processEWMail(mailno)
    return True

def autorunWFComments(projectname : str) -> bool:
    #Run WFComments for mail's project
    initProject(outlookconfig, projectname, "projectnames")
    WorkflowComments.main(inputUseTextFile="n", forceAll=True) #force all for now
    config.info("WorkflowComments ran successfully.")
    return True

def autorunRFITracker(outlookconfig, projectname : str) -> bool:
    initProject(outlookconfig, projectname, "projectnames")
    RFITracker.main()
    config.info("RFITracker ran successfully.")
    return True

#find project details from csv using the parsed projectname / code
# init on that project
def initProject(outlookconfig : OutlookConfig, search_term : str, search_for : str = "projectnames"):
    projectslist: dict[str, list] = getProjectsList()

    projectvals: list[str] = project_list_extract(projectslist, search_for)

    count = 0
    while search_term not in projectvals:
        if count > 1:
            raise Exception("Cannot find project on Aconex. Major L")
        config.warning("Project not found in list - re-running getAllProjects")
        count += 1
        outlookconfig.initWrapper(debug=None)
        getAllProjects.main()
        projectslist = getProjectsList()
        projectvals = project_list_extract(projectslist, search_for)

    projectindex = projectvals.index(search_term)
    projectid = list(projectslist.keys())[projectindex]
    projectname = list(projectslist.values())[projectindex][0]
    projectcode = list(projectslist.values())[projectindex][1]

    outlookconfig.initWrapper(debug=[projectname, projectid, projectcode])
    config.debug(f"{config.projectname()=}")


def project_list_extract(projectslist: dict[str, list], search_for: str) -> list[str]:
    projectvals: list[str]

    if search_for == "projectnames":
        projectvals, _ = zip(*projectslist.values())
    elif search_for == "projectcodes":
        _, projectvals = zip(*projectslist.values())
    return projectvals


main()
