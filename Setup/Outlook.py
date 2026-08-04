import re
from typing import Any

from Setup import EAsetup, UK1setup
from Setup.Project import getProjectsList
from Setup.config import config, init
from Setup.getAllProjects import getAllProjects
from b_Workflow import WorkflowComments
from d_Mail.RFIs import RFITracker
from f_AutoMail.EW import EWExcel


class OutlookConfig:
    def __init__(self, debug = False):
        self.bearer = EAsetup.bearer if debug else UK1setup.bearer
        self.env = EAsetup.env if debug else UK1setup.env

    def initWrapper(self, debug=None):
        init(self.bearer, self.env, debug)


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
    import win32com.client

    # connect to open outlook application - must be open on the machine for this to work
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNameSpace('MAPI')
    except AttributeError:
        raise AttributeError("Could not run. Outlook is not open.")
    return outlook


def getLastRan() -> str:
    with open(config.getOutlookLastRanLocation(), "r") as file:
        strDateLastRan = file.read()
        file.close()

    return strDateLastRan


def checkEmail(debug : bool, item : object, runset : set[tuple]) -> list[tuple|bool|None]:
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
        success = autorunWFComments(debug, projectname)
        runagain = False #do not need to run this more than once at a time

    elif mailTypeCode == "RFI" or mailTypeCode == "SUBRFI" or mailTypeCode == "RTSCRFI" or mailTypeCode == "RTRFI":
        config.debug("Running rfiTracker for projectname %s" % projectname)
        success = autorunRFITracker(debug, projectname)
        runagain = False

    #EARLY WARNINGS
    elif mailTypeCode == "EWN" or mailTypeCode == "EC-EWN":
        if projectname in ["Wolverhampton Police", "Stechford Police", "HB Test"]:
            config.debug("Running sendEWExcel for projectname %s" % projectname)
            mailno = getmailno(subject)
            config.debug(f"{mailno=}")
            success = sendEWExcel(debug, projectname, mailno)
        runagain = True

    #If code ran successfully, ignore this email in future
    if success:
        item.Categories = 'Python Parsed'
        item.Save()
        config.info("Categorised mail.")

    if not runagain:
        return [(projectname, mailTypeCode), success]

    return [None, success]


def getmailno(subject : str) -> str:
    splsub = subject.split(":")
    if len(splsub) < 2:
        raise Exception("Cannot parse mail type from subject.")

    return splsub[0]


def sendEWExcel(debug : bool, projectname: str, mailno: str) -> bool:
    initProject(projectname, "projectnames", debug)
    EWExcel.processEWMail(mailno)
    return True


def autorunWFComments(debug : bool, projectname : str) -> bool:
    #Run WFComments for mail's project
    initProject(projectname, "projectnames", debug)
    WorkflowComments.main(inputUseTextFile="n") #force all for now
    config.info("WorkflowComments ran successfully.")
    return True


def autorunRFITracker(debug : bool, projectname : str) -> bool:
    initProject(projectname, "projectnames", debug)
    RFITracker.main()
    config.info("RFITracker ran successfully.")
    return True


def initProject(search_term : str, search_for : str = "projectnames", debug : bool = False):
    projectslist: dict[str, list] = getProjectsList()
    outlookconfig = OutlookConfig(debug)
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


EMAIL1ID = "http://schemas.microsoft.com/mapi/id/{00062004-0000-0000-C000-000000000046}/80850102"

def getEmAddress(contact) -> str:
    if contact.Email1AddressType == "SMTP":
        return contact.Email1Address

    elif contact.Email1AddressType == "EX":
        outlook = connect()
        propertyaccessor = contact.PropertyAccessor

        recipientEntryID = propertyaccessor.BinaryToString(propertyaccessor.GetProperty(EMAIL1ID))
        recipient = outlook.Application.Session.GetRecipientFromID(recipientEntryID)

        if recipient and recipient.Resolve() and recipient.AddressEntry:
            euser = recipient.AddressEntry.GetExchangeUser()
            em = euser.PrimarySmtpAddress

            config.logger.debug("EXC email converted to {em}".format(em=em))
            return em

        else: return ""

    else: return ""
