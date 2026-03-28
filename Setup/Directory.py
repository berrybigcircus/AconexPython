import json
import re

import win32com.client

from Setup.APIcommon import session, getAPIResponse, postAPIResponse
from Setup.Project import Project

import xml.etree.ElementTree as ET  # for parsing xml


class AconexUser():
    def __init__(self, name, org, disttype):
        self.__name : str = name
        self.__org : str = org
        self.__disttype : str = disttype

    def name(self) -> str:
        return self.__name

    def org(self) -> str:
        return self.__org

    def wasSentFrom(self) -> bool:
        return self.__disttype == "FROM"

    def wasSentTo(self) -> bool:
        return self.__disttype == "TO" #if it was to them, not cc, bcc, or sent by them


class OutlookMail:
    def __init__(self):
        self.to : set[str] = None
        self.cc: set[str] = None
        self.subject : str = None
        self.body : str
        self.setSubject()

    # Abstract
    def setSubject(self):
        pass

    #TODO validate emails before sending
    def setTo(self, tol : list[str]):
        self.to = set(tol)

    def setCC(self, ccl: list[str]):
        self.cc = set(ccl)

    def createBody(self, draftsubject):
        # Find the draft in my Outlook drafts
        outlook = win32com.client.Dispatch("Outlook.Application").GetNameSpace('MAPI')
        draftsfolder = outlook.GetDefaultFolder(16).Items
        draftsfolder = draftsfolder.Restrict("[Subject] = '{draftsubject}'".format(draftsubject=draftsubject))

        assert (len(draftsfolder) == 1)
        draftemail = draftsfolder[0]
        self.body = draftemail.HTMLBody

    def draftEmail(self):
        olMailItem = 0x0
        obj = win32com.client.Dispatch("Outlook.Application")
        newMail = obj.CreateItem(olMailItem)
        newMail.To = "; ".join(self.to) if self.to else ""
        newMail.cc = "; ".join(self.cc) if self.cc else ""
        newMail.BodyFormat = 2
        newMail.HTMLBody = self.body
        newMail.Subject = self.subject
        newMail.display(True)


class NewUserEmail(OutlookMail):
    def __init__(self, p : Project, orgadmins : list[str]):
        self.company : str
        self.project : Project = p
        super().__init__()
        self.setSubject()
        self.createBody("NewUser")
        self.body = self.body.replace("PROJECT", self.project.projectName())
        self.setOrgAdmins(orgadmins)

    def setSubject(self):
        self.subject = self.project.projectCodePrefix() + "Aconex New User Access"

    def setOrgAdmins(self, orgadmins: list[str]):
        super().setTo(orgadmins)
        self.body = self.body.replace("###", "<br>".join(orgadmins))


class NewOrgEmail(OutlookMail):
    def __init__(self, p : Project):
        self.company: str
        self.project: Project = p
        super().__init__()
        self.createBody("NewOrg")
        self.body = self.body.replace("PROJECT", self.project.projectName())

    def setSubject(self):
        self.subject = self.project.projectCodePrefix() + "Aconex CDE Organisation Registration"


def addUserIds(root, elemname : str, userids : set[str]):
    for uid in userids:
        elem = ET.Element(elemname)
        elem.text = uid
        root.append(elem)

def addDocIds(root, docids : list[str]):
    pass


def getMailingGroups(config):
    session.cache.clear()
    url = config.env() + "/api/mailinggroups/" + config.project().projectID() #they structured the url different for no reason
    headers = {'Authorization': config.bearer()}
    mgResponse = getAPIResponse(url, headers, "finding mailing groups") #it returns some json garbo not xml
    jsonMG = json.loads(mgResponse)

    return jsonMG


def findMailingGroup(jsonMG, regSearch) -> (str, [str]):
    #find MG from returned list of mailing groups (if it exists), using regex search term on the group name
    mailingGroups = jsonMG["mailingGroups"] #list of groups
    mgID = 0
    mgUsers = []

    if mailingGroups == None: return mgID, mgUsers

    for group in mailingGroups:
        if re.search(regSearch, group["groupName"]):
            mgID = group["groupId"]
            mgUsers = [user["userId"] for user in group["users"]] if group["users"] != None else [] #extract just the id
            break

    return mgID, mgUsers

#Find users from multiple groups in one go
def findMailingGroups(config, groupnames: list[str]):
    jsonMG = getMailingGroups(config)
    mailingGroups = jsonMG["mailingGroups"]  # list of groups
    if mailingGroups == None: return

    matchedgroups = list(filter(lambda group : group["groupName"] in groupnames, mailingGroups))
    mgIds = []
    userIds = set()
    for group in matchedgroups:
        mgIds.append(group["groupId"])
        userIds.update([str(user["userId"]) for user in group["users"]] if group["users"] is not None else [])

    if len(matchedgroups) != len(groupnames):
        config.logger.warning("Not all group names were found in the mailing groups of the project.")

    return mgIds, userIds


def createMailingGroup(config, groupName):
    url = config.env() + "/api/mailinggroups/" + config.project().projectID()
    headers = {'Authorization': config.bearer()}

    jsonData = {"groups": [{
        "groupName": groupName,
        "isLocked": "false"
        }]}
    response = postAPIResponse(url=url, headers=headers, body=jsonData, explanation="creating mailing group")

    config.info("'%s' mailing group created." % groupName)
    session.cache.clear()
    mgResponse = getAPIResponse(url, headers, "finding mailing groups") #it doesn't return the id of the new group, so have to run the get again
    jsonMG = json.loads(mgResponse)

    searchTerm = "^" + groupName + "$" #should be able to search exact for any mailing group as it was just created with this name
    return findMailingGroup(jsonMG, searchTerm)
