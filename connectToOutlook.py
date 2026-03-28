import pathlib
from datetime import datetime

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

def main():
    #connect to open outlook application - must be open on the machine for this to work
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNameSpace('MAPI')
    except AttributeError:
        raise AttributeError("Could not run. Outlook is not open.")

    aconexfolder : object
    #get my account, find Aconex folder
    for i in range(1,outlook.Folders.Count+1):
        root = outlook.folders.Item(i)
        if root.Name == "nicole.millinship@henrybrothers.co.uk":
            aconexfolder = root.Folders["Aconex"]

    if not aconexfolder:
        raise Exception("No Aconex outlook folder found")

    aconexmessages = aconexfolder.items
    aconexmessages.Sort("[ReceivedTime]", True) #ensure sorted by date received

    lastRan: str = getLastRan()
    latestmessages = aconexmessages.Restrict("[ReceivedTime] >= '" + lastRan + "'")
    latestmessages = latestmessages.Restrict("Not([Categories] = 'Python Parsed')")
    config.debug(f"{latestmessages.Count=}")
    latestmessages.Sort("[ReceivedTime]", False) #start with the oldest

    global bearer
    bearer = EAsetup.bearer if DEBUG else UK1setup.bearer
    global env
    env = EAsetup.env if DEBUG else UK1setup.env

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
    initProject(projectname)
    EWExcel.processEWMail(mailno)
    return True

def autorunWFComments(projectname : str) -> bool:
    #Run WFComments for mail's project
    initProject(projectname)
    WorkflowComments.main(inputUseTextFile="n", forceAll=True) #force all for now
    config.info("WorkflowComments ran successfully.")
    return True

def autorunRFITracker(projectname : str) -> bool:
    initProject(projectname)
    RFITracker.main()
    config.info("RFITracker ran successfully.")
    return True

#find project details from csv using the parsed projectname
# init on that project
def initProject(projectname : str):
    projectslist: dict[str, list] = getProjectsList()

    projectnames: list[str]
    projectnames, _ = zip(*projectslist.values())

    count = 0
    while projectname not in projectnames:
        if count > 1:
            raise Exception("Cannot find project on Aconex. Major L")
        config.warning("Project not found in list - re-running getAllProjects")
        count += 1
        init(bearer, env, debug=None)
        getAllProjects.main()
        projectslist = getProjectsList()
        projectnames, _ = zip(*projectslist.values())

    projectindex = projectnames.index(projectname)
    projectid = list(projectslist.keys())[projectindex]
    projectcode = list(projectslist.values())[projectindex][1]

    init(bearer, env, debug=[projectname, projectid, projectcode])

main()
