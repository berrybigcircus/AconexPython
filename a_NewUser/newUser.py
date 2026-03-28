import csv
import pathlib

import requests #for making http requests
import json #for reading json
from urllib.parse import urlencode, quote_plus
import xml.etree.ElementTree as ET #for parsing xml
import re #regex
import webbrowser
import datetime
import pandas
import win32com.client

from Setup.APIcommon import session, getAPIResponse, indexInput, cleanOrgName, SelLogIn, loadCookies, writeCookies
from Setup.Mail import getProjectInviteMailID, openDraftLink
from Setup.Directory import OutlookMail, NewUserEmail, NewOrgEmail, getMailingGroups, findMailingGroup, \
    createMailingGroup
from Setup.config import config

CSVPATH = r"C:\Users\nicole.millinship\OneDrive - Henry Brothers Ltd\CLP - Docs\General\#Other Files\Aconex\OrgAdminList.csv"

global FOLDERPATH
FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())

NUTRACKERPATH = r"C:\Users\nicole.millinship\OneDrive - Henry Brothers Ltd\CLP - #Docs\General\#Other Files\Aconex\Aconex New Users Tracker.xlsm"
nuTracker = { #the headings of the new user tracker
    "User": [],
    "Company": [],
    "Project": [],
    "Org Admin(s)": [],
    "Done?": [],
    "Action with": [],
    "Comments": [],
    "Date Started": [],
    "Date Completed": [],
}

EMAIL1ID = "http://schemas.microsoft.com/mapi/id/{00062004-0000-0000-C000-000000000046}/80850102"

class OutlookContact:
    def __init__(self, contactitem, aconexid):
        self.contactitem = None
        self.__email : str = None
        self.__mobile : str = None
        self.__role : str = None
        self.__aconexID : str = None

        if contactitem:
            config.logger.info("Creating OutlookContact object")
            self.contactitem = contactitem
            self.__email = self.getEmAddress(contactitem)
            self.__mobile = contactitem.MobileTelephoneNumber
            self.__role = contactitem.JobTitle
            self.__aconexID = contactitem.GovernmentIDNumber
            self.setaconexid(aconexid)
            config.logger.debug(", ".join([self.__email, self.__mobile, self.__role, self.__aconexID]))

    def getEmAddress(self, contact) -> str:
        if contact.Email1AddressType == "SMTP":
            return contact.Email1Address

        elif contact.Email1AddressType == "EX":
            outlook = win32com.client.Dispatch("Outlook.Application").GetNameSpace('MAPI')
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

    def email(self) -> str:
        return self.__email if self.__email else ""

    def mobile(self) -> str:
        return self.__mobile if self.__mobile else ""

    def role(self) -> str:
        return self.__role if self.__role else ""

    def setaconexid(self, aid : str):
        if not self.__aconexID:
            self.__aconexID = aid
            self.contactitem.GovernmentIDNumber = aid
            self.contactitem.Save()
            config.logger.info("Outlook Contact updated with ID {i}".format(i=self.contactitem.GovernmentIDNumber))

def searchForCompany(companyname, usersFilter):
    parameters = {"org_name": companyname}
    url = config.env() + "/api/directory?" + urlencode(parameters)
    return directorySearch(url, usersFilter, False)

def globalDirectorySearch(parameters: dict) -> (str, OutlookMail):
    DAYSLIMIT : int = 90
    url = config.env() + "/api/directory?" + urlencode(parameters)
    # search for users (don't include guests)
    usersFilter = "SearchResults/Directory[SearchResultType!='GUEST_TYPE']"
    userXML, _ = directorySearch(url, usersFilter, True)

    if userXML is None: #if not in global directory
        nuTracker["Done?"].append("No")

        companyname = cleanOrgName(input("Enter the company name: "))
        orgid, orgname = searchForCompany(companyname, usersFilter)

        #If company not found in directory
        if orgid is None:
            nuTracker["Company"].append(companyname) #you may need to edit later
            nuTracker["Action with"].append("User")
            nuTracker["Comments"].append("New org")
            omail = NewOrgEmail(config.project())
            return "neworg", omail

        orgadmins : list[str] = None
        datechecked : datetime.datetime = None

        # look up org id in csv to find org admins
        orgname, orgadmins, datechecked = csvOrgAdminList.get(orgid) or (_, None, None)

        #no data in csv or last checked too long ago
        while orgadmins is None or datechecked < (datetime.datetime.today() - datetime.timedelta(days=DAYSLIMIT)):
            jsonRes = FindOrgAdmins(orgid)
            if jsonRes is None:
                return "Error", None
            config.logger.debug(jsonRes)
            orgadmins = parseOrgAdmins(json.loads(jsonRes), False)

            if orgadmins is None:
                tryagain: str = input("Do you want to search company name again? (Y/N)")
                if tryagain.lower() != "y":
                    nuTracker["Company"].append(companyname)  # you may need to edit later
                    nuTracker["Action with"].append("User")
                    nuTracker["Comments"].append("New org")
                    omail = NewOrgEmail(config.project())
                    return "neworg", omail

            else:
                datechecked = datetime.datetime.now()
                break

        updateOrgAdminCSV(orgid, orgname, orgadmins, datechecked)
        config.info("Drafting email to org admins - %s" % ", ".join(orgadmins))

        nuTracker["Action with"].append("Org admin")
        nuTracker["Comments"].append("New user")
        omail = NewUserEmail(config.project(),orgadmins)
        return "newuser", omail

    #If in global directory
    else:
        orgname = userXML.find('OrganizationName').text
        username = userXML.find('UserName').text

        helperparams = {"PROJECT_ID": config.project().projectID(),
                        "ORG_NAME": orgname,
                        "LAST_NAME": username.split(' ')[-1]}
        urlhelper = config.env() + "/hub/index.html?mainTarget=" + quote_plus("/SearchDirectory?DIRECTORY=ACONEX&") + quote_plus(urlencode(helperparams))
        webbrowser.open(urlhelper)
        input("Opening link, please add them to the required project...")
        return "rerun", None


# Find out the org admin(s)
# there is no api request for org admins, but the xml is available on the web. This means we need to log in and get the cookies for a logged in session
def FindOrgAdmins(orgid) -> str | None:
    url = config.env() + "/internal/projects/" + config.project().projectID() + "/organizations/" + orgid + "/orgAdmins?count=200"
    config.logger.info(url)

    #try with existing cookies saved to txt file in case session is still valid
    _, cj = loadCookies(config)
    jsonRes = session.get(url, headers=None, cookies=cj)

    if jsonRes.status_code == 404:
        config.logger.debug("Could not make request from existing cookies. Opening browser to log in...")
        _, cj = SelLogIn(config)

        jsonRes = session.get(url, headers=None, cookies=cj)

    if jsonRes.status_code != 200:
        print("There was an error getting the org admins %d %s" % (jsonRes.status_code, jsonRes.reason))

    return jsonRes.text


#Bulk CSV org admin updater to cover orgs on current projects
def bulkUpdateCSV():
    csvOrgAdminList = loadcsv()
    oglen = len(csvOrgAdminList)
    DAYSLIMIT: int = 90

    projectsList: dict[str, list] = ProjectClasses.getProjectsList()
    projecturls = [config.ACONEXENV + "/api/projects/" + pid for pid in projectsList.keys()]
    orgs: dict[str, str] = {}

    for purl in projecturls:
        orgs.update(getAllOrgsOnProject(purl))

    config.logger.debug("%d orgs found" % len(orgs))

    for (orgid, orgname) in orgs.items():
        config.logger.debug(orgname)

        orgadmins: list[str] = None
        datechecked: datetime.datetime = None

        # look up org id in csv to find org admins
        _, orgadmins, datechecked = csvOrgAdminList.get(orgid) or (None, None, None)

        # no data in csv or last checked too long ago
        if orgadmins is None or datechecked < (datetime.datetime.today() - datetime.timedelta(days=DAYSLIMIT)):
            jsonRes = FindOrgAdmins(orgid)
            if jsonRes is None:
                continue
            config.logger.debug(jsonRes)
            orgadmins = parseOrgAdmins(json.loads(jsonRes), assumeOK = True)

            if orgadmins is None:
                config.logger.error("Could not parse org admins for company %s" % orgname)

            else:
                datechecked = datetime.datetime.now()
                config.logger.debug("{orgid}: {orgname} {orgadmins} ({datechecked})".format(orgid=orgid, orgname=orgname, orgadmins=orgadmins, datechecked=datechecked))
                csvOrgAdminList[orgid] = (orgname, orgadmins, datechecked)

    #Write entire orgadminlist back.
    assert len(csvOrgAdminList) >= oglen #check it's not gone terribly wrong
    writeOrgAdminCSV(csvOrgAdminList)

#Get the org names and IDs of orgs on the selected project
def getAllOrgsOnProject(projecturl : str) -> dict[str, str]:
    headers = {'Authorization': config.bearer()}
    parameters = {"show_groups": "False"}
    url = projecturl + "/directory?" + urlencode(parameters)

    xml = getAPIResponse(url, headers, "searching the directory")
    root = ET.fromstring(xml)
    dirresults = {res.find("OrganizationId").text: res.find("OrganizationName").text for res in root.findall("SearchResults/Directory")}

    return dirresults

#Write whole org admin based on dictionary var
def writeOrgAdminCSV(csvOrgAdminList):
    csvfile = open(CSVPATH, 'w', newline='')
    writer = csv.writer(csvfile, delimiter=',')
    writer.writerow(["Org ID", "Company", "Org Admin(s)", "Date Checked"]) #put header in
    rows = [[k, v[0], "; ".join(v[1]), v[2].strftime("%d/%m/%Y")] for k, v in csvOrgAdminList.items()]
    writer.writerows(rows)
    config.logger.info("csv file re-written")

def updateOrgAdminCSV(orgid : str, orgname : str, orgadmins : list[str], datechecked : datetime):
    strdateChecked = datechecked.strftime("%d/%m/%Y")
    combOrgAdmins = "; ".join(orgadmins)
    newRow = [orgid, orgname, combOrgAdmins, strdateChecked]

    #if this org was already in the csv
    if orgname in csvOrgAdminList.keys():
        #we will have to rewrite the whole csv, no other way with csv files
        csvOrgAdminList[orgid] = (orgname, orgadmins, datechecked)

        rows = [[k, v[0], "; ".join(v[1]), v[2].strftime("%d/%m/%Y")] for k, v in csvOrgAdminList.items()]

        csvfile = open(CSVPATH, 'w', newline='')
        writer = csv.writer(csvfile, delimiter = ',')
        writer.writerow(["Org ID", "Company", "Org Admin(s)", "Date Checked"]) #put header in
        writer.writerows(rows)
        config.logger.info("Updated row %s in orgadmins.csv" % orgname)
    else:
        csvfile = open(CSVPATH,'a', newline='')
        writer = csv.writer(csvfile, delimiter = ',')
        writer.writerow(newRow)
        csvfile.close()
        csvOrgAdminList[orgid] = (orgname, orgadmins, datechecked)
        config.logger.info("Added %s to orgadmins.csv as new row" % orgname)

#convert xml to a list of org admin names/emails separated by ;
def parseOrgAdmins(jsonRes, assumeOK : bool = False) -> list[str] | None:
    numResults = int(jsonRes["totalNumberOfOrgAdmins"])
    if numResults == 0:
        config.logger.warning("No org admins in this company. Check if this org is a guest")
        return None
    oaArr = jsonRes["orgAdmins"]
    orgAdminList = list(set([(oa['name'] + " <" + oa['email'] + ">") for oa in oaArr]))
    print("Org admins found: " + ",".join(orgAdminList))

    if not assumeOK:
        inputCheck = input("Look okay? (Y/N): ")
        if inputCheck.upper() != "Y":
            return None

    return orgAdminList

def projectDirectorySearch(parameters):
    session.cache.clear()
    url = config.projecturl() + "/directory?" + urlencode(parameters)
    chosenUser, _ = directorySearch(url, "SearchResults/Directory", True)

    isHB = chosenUser.find("OrganizationName").text == "Henry Brothers" if chosenUser else False
    if isHB:  # if they are in henry brothers, add to HB confidential as well
        groupid, _ = findMailingGroup(getMailingGroups(), "HB Confidential")
        statuscode, reason = addUserstoMG(groupid,[chosenUser.find("UserId").text])
        if statuscode == 200:
            config.info("Henry Brothers user added to HB Confidential.")
        else:
            config.error("There was an error adding HB user to HB Confidential. " + reason)

    return chosenUser

def directorySearch(url, searchfilter, userSearch=True) -> tuple[ET.Element | None | str, None | str]:
    headers = {'Authorization': config.bearer()}
    xml = getAPIResponse(url, headers, "searching the directory")
    root = ET.fromstring(xml)
    numFound = int(root.attrib['TotalResults'])

    if numFound == 0:
        config.info("No %s found with those details." % ("users" if userSearch else "orgs"))
        return None, None
    elif numFound > 1:
        toFind = root.findall(searchfilter)
        if toFind is None: #if all the users found were guests
            print("No %s found with those details." % ("users" if userSearch else "orgs"))
            return None, None

        if userSearch: #list the different users
            print("%d results found:" % numFound)
            for i, user in enumerate(toFind):
                print("    %d - %s of %s" % (i, user.find('UserName').text, user.find('OrganizationName').text))
            userIndex = indexInput(len(toFind) - 1)
            if userIndex == 0:
                return (toFind[userIndex], None)
            else:
                return None, None if userIndex is None else (toFind[userIndex], None)

        else: #list the different orgs
            uniqueOrgs = list(set([(user.find('OrganizationId').text, user.find('OrganizationName').text) for user in toFind]))
            print("%d results found:" % len(uniqueOrgs))
            for i, (id, name) in enumerate(uniqueOrgs):
                print("    %d - %s (%s)" % (i, name, id))
            #TODO - what do we do if multiple orgs are the 'right' one? what if none are?
            orgIndex = indexInput(len(uniqueOrgs) - 1)
            return (None, None) if orgIndex is None else (uniqueOrgs[orgIndex])
    else:
        if userSearch:
            return root.find('SearchResults/Directory'), None  # return singular user
        else:
            orgXML = root.find('SearchResults/Directory')
            return orgXML.find('OrganizationId').text, orgXML.find('OrganizationName').text


def addToAll(userData):
    #check for existence of All group
    jsonMG = getMailingGroups(config)
    
    mgID, mgUsers = findMailingGroup(jsonMG, "^All($| ).*")

    if mgID == 0: #'All' not found
        mgID, mgUsers = createMailingGroup("All")

    usersToAdd = [dirUser.find("UserId").text for dirUser in userData if int(dirUser.find("UserId").text) not in mgUsers] #list the user ID of users not already in the mailing group

    if len(usersToAdd) == 0:
        config.info ("The users are in the 'All' mailing group already.")
        return

    #Add to 'All'
    statuscode, reason = addUserstoMG(mgID, usersToAdd)

    if statuscode != 200:
        config.error("There was an error adding the users to the 'All' mailing group. %s" % reason)
    else:
        config.info("Users added to 'All' mailing group successfully.")

def addUserstoMG(mgID, usersToAdd):
    url = config.env() + "/api/mailinggroups/" + config.project().projectID() + "/addUsers"
    headers = {'Authorization': config.bearer()}
    jsonData = {"addOrRemoveUsersGroupRequest": [{
                    "groupId": mgID,
                    "userId": usersToAdd
                }]}

    response = requests.put(url, headers=headers, json=jsonData)

    return response.status_code, response.reason

def addToGroup(userData):
    session.cache.clear()
    jsonMG = getMailingGroups(config)

    for dirUser in userData: #must check each user's org
        userName = dirUser.find("UserName").text
        userID = int(dirUser.find("UserId").text)


        orgName = dirUser.find("TradingName").text #trading name is what displays on the directory
        filteredOrgName = cleanOrgName(orgName)
        regSearch = ".*" + filteredOrgName + ".*"
        mgID, mgUsers = findMailingGroup(jsonMG, regSearch)

        if mgID == 0: #Group not found
            regSearch = ".*" + filteredOrgName.split(" ")[0] + ".*" #search on first word in company name
            mgID, mgUsers = findMailingGroup(jsonMG, regSearch)

            if mgID == 0:
                mgID, mgUsers = createMailingGroup(config, filteredOrgName)
                session.cache.clear()
                jsonMG = getMailingGroups(config) #need to refresh MG list

        if userID not in mgUsers:
            statuscode, reason = addUserstoMG(mgID, [userID])

            if statuscode != 200:
                config.error("There was an error adding user %s to the mailing group. %s" % (userName, reason))
            else:
                config.info("User %s added to mailing group successfully." % userName)
        
        else:
            config.info("User %s is already in the mailing group." % userName)

def draftTransmittal(userData):
    #get HBDC All #Docs
    HBDCALLDOCS = "matchAll:1 confidential:0 AND NOT (SharedWith_singleSelect:Internal* OR SharedWith_singleSelect:Shared*)" #manual recreation of this search
    parameters = {"search_type": "PAGED", #PAGED, meaning return results by "pages" of variable size.
                  "return_fields": "docno,title,doctype,confidential,SharedWith_singleSelect", 
                  "search_query": HBDCALLDOCS,
                  "page_size": "500"
                  } 

    headers = {'Authorization': config.bearer()}
    url = config.projecturl() + "/register?" + urlencode(parameters)

    xml = getAPIResponse(url, headers, "searching document register")

    searchXml = ET.fromstring(xml.strip()).findall('SearchResults/')
    totalPages: int = int(ET.fromstring(xml.strip()).get('TotalPages'))

    currentPageNum = 1
    while currentPageNum < totalPages:
        currentPageNum += 1
        url = config.projecturl() + "/register?" + urlencode(parameters) + "&page_number=" + str(currentPageNum)
        xml = getAPIResponse(url, headers, "searching document register")
        searchXml.extend(ET.fromstring(xml.strip()).findall('SearchResults/'))

    docIds = [doc.attrib['DocumentId'] for doc in searchXml]
    userIds = [dirUser.find("UserId").text for dirUser in userData]

    #draft transmittal
    url = config.projecturl() + "/mail?is_draft=true"
    headers = {'Authorization': config.bearer(),
                'Content-Type': 'multipart/mixed',
                'boundary': 'myboundary'}

    xmlFile = open(FOLDERPATH + "\\xmlFiles\\allTransmittal.xml", "r")
    xmlData = xmlFile.read()
    xmlFile.close()

    xmlData = xmlData.replace("ATTACHMENT_COUNT_GOES_HERE",str(len(docIds)))

    xmlData = addUsersAndDocs(xmlData, userIds, docIds)

    response = requests.post(url, headers=headers, data=xmlData)

    if response.status_code != 200:
        config.error("There was an error in drafting the transmittal. %s" % response.reason)
        return False

    config.info("Draft transmittal created.")
    openDraftLink(config, response.text)

    return True

def addUsersAndDocs(xmlData, userIds, docIds): #put users and documents into mail xml
    for uId in userIds: #add users, each with a tag
        userStr = "<ToUserId>" + uId + "</ToUserId>\nTO_USERS_GO_HERE"
        xmlData = xmlData.replace("TO_USERS_GO_HERE", userStr)

    xmlData = xmlData.replace("TO_USERS_GO_HERE\n", "")
    
    for dId in docIds:
        attachStr = "--myboundary\n\nX-documentId: " + dId + "\n\n"
        xmlData = xmlData + attachStr

    xmlData = xmlData + "--myboundary--"
    return xmlData

def addWorkingDays(startdate, daysToAdd): #fcking can't believe i have to include response required in the xml of create mail so i have to manaully do thhis
    busDaysToAdd = daysToAdd
    currentdate = startdate
    while busDaysToAdd > 0:
        currentdate += datetime.timedelta(days=1)
        weekday = currentdate.weekday()
        if weekday >= 5: # mon = 0, sat = 5, sun = 6
            continue #skip weekends
        busDaysToAdd -= 1
    
    return currentdate

def draftProjectInvite(userData):
    #get the project invite drafts that have been pre-made
    parameters = {"search_type": "PAGED",
              "mail_box": "draftbox",
              "return_fields": "docno,subject,responsedate,attachedDocumentCount",
              "search_query": "corrtypeid:" + getProjectInviteMailID(config.mailtypes()) #get project invite mail types only
              }

    url = config.projecturl() + "/mail?" + urlencode(parameters)
    headers = {'Authorization': config.bearer()}
    response = requests.get(url, headers=headers)
    xml = ET.fromstring(response.text.strip())

    searchXml = xml.findall('SearchResults/Mail')
    inviteTypes = [mail.find('Subject').text for mail in searchXml]

    #ask user to choose project invite draft type
    print("Invite types available on this project:")
    for i, inv in enumerate(inviteTypes): #output options to user
        print("    %d - %s" % (i, inv))

    chosenInviteSubj = inviteTypes[indexInput(len(inviteTypes)-1)]
    chosenInviteMail = xml.find("SearchResults/Mail[Subject='{}']".format(chosenInviteSubj))

    #get entire mail metadata for that project invite draft
    url = config.projecturl() + "/mail/" + chosenInviteMail.attrib['MailId'] #view mail metadata
    response = requests.get(url, headers=headers)
    draftMailXML = ET.fromstring(response.text.strip())

    if response.status_code != 200:
        config.error("There was an error getting data about the draft mail. %s" % response.reason)
        return
    
    #create mail
    url = config.projecturl() + "/mail?is_draft=true"
    headers = {'Authorization': config.bearer(),
                'Content-Type': 'multipart/mixed',
                'boundary': 'myboundary'}

    docCount = chosenInviteMail.find('AttachedDocumentCount').text

    xmlFile = open(FOLDERPATH + "\\xmlFiles\\inviteMail.xml", "r")
    xmlData = xmlFile.read()
    xmlFile.close()

    xmlData = xmlData.replace("SUBJECT_GOES_HERE", "Project Invite") #idk what to do with the subject, depends if everyone you're sending it to is from one org or not
    xmlData = xmlData.replace("ATTACHMENT_COUNT_GOES_HERE", docCount)
    resDate = addWorkingDays(datetime.datetime.now(datetime.timezone.utc), 2)
    resDate = resDate.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    xmlData = xmlData.replace("RESPONSE_REQ_DATE_HERE", str(resDate))
    xmlData = xmlData.replace("MAILID_GOES_HERE", getProjectInviteMailID(config.mailtypes()))
    
    mBody = "<![CDATA[" + draftMailXML.find('MailData').text + "]]>"
    xmlData = xmlData.replace("MAIL_BODY_HERE", mBody)

    attachments = draftMailXML.findall('Attachments/RegisteredDocumentAttachment')
    docIds = [doc.find('DocumentId').text for doc in attachments]

    userIds = [dirUser.find("UserId").text for dirUser in userData]

    xmlData = addUsersAndDocs(xmlData, userIds, docIds)

    response = requests.post(url, headers=headers, data=xmlData)
    if response.status_code != 200:
        config.error("There was an error drafting the project invite mail. %s" % response.reason)
        return

    config.logger.info("Draft project invite created.")
    openDraftLink(config, response.text)


dirCreator = { #headings for csv for project directory
    "Name": [],
    "Company / Works": [],
    "Role": [],
    "Contact Number": [],
    "Address": [],
    "Email": []
}

def createProjectDirectory():
    parameters = {"show_groups": "true"}
    url = config.projecturl() + "/directory?" + urlencode(parameters)
    headers = {'Authorization': config.bearer()}
    xml = getAPIResponse(url, headers, "searching the directory")
    root = ET.fromstring(xml)
    groups = root.findall("SearchResults/Directory[SearchResultType='GROUP_TYPE']")

    filterOutRegex = "All|HB.*|(Henry Brothers).*|Client.*|(Int Design Team)"
    for group in groups:
        groupname = group.find("GroupName").text
        groupid = group.find("GroupId").text

        if re.search(filterOutRegex, groupname):
            continue
        else:
            bracketsplit = groupname.split("(")
            if len(bracketsplit) != 2: continue
            companyname = bracketsplit[0]
            descworks = bracketsplit[1].replace(")","")

            #find users in this mailing group
            url =  config.projecturl() + "/groups/" + groupid
            headers = {'Authorization': config.bearer()}
            xml = getAPIResponse(url, headers, "listing the users in the mailing group")
            searchXml = ET.fromstring(xml.strip()).findall('SearchResults/')

            if len(searchXml) < 1: continue

            #check all the users for address - in case they are in different org variations, one might have an address
            iterator = iter(searchXml)
            while True:
                try:
                    orgaddress = createAddress(next(iterator))
                    config.debug(orgaddress)
                except StopIteration: #at end of list
                    break
                if orgaddress != "":
                    break

            for userXml in searchXml:
                lastname = userXml.find("UserLastName").text.title()
                fullname = userXml.find("UserFirstName").text.title() + " " + lastname
                contact = outlooklookup(fullname,lastname,companyname,userXml.find("UserId").text)

                dirCreator["Name"].append(fullname)
                dirCreator["Role"].append(userXml.find("JobTitle").text or contact.role())
                contactnum = contact.mobile() or userXml.find("Mobile").text or userXml.find("Phone").text
                dirCreator["Contact Number"].append(contactnum)
                dirCreator["Company / Works"].append(groupname)
                dirCreator["Address"].append(orgaddress) #TODO - look up address on web??? possible?
                dirCreator["Email"].append(contact.email())

    #add HB users
    session.cache.clear()
    parameters = {"org_name": "Henry Brothers",
                  "show_groups": "false"}
    url = config.projecturl() + "/directory?" + urlencode(parameters)
    headers = {'Authorization': config.bearer()}
    xml = getAPIResponse(url, headers, "searching for Henry Brothers")
    root = ET.fromstring(xml)
    toFind = root.findall("SearchResults/Directory[SearchResultType!='GUEST_TYPE']")
    for user in toFind:
        fullname = user.find('UserName').text
        if fullname == "HB Drawings": continue

        contact = outlooklookup(fullname, fullname.split(" ")[1], "Henry Brothers", user.find("UserId").text)

        dirCreator["Name"].append(fullname)
        dirCreator["Role"].append(user.find("JobTitle").text)
        dirCreator["Contact Number"].append(user.find("Mobile").text or contact.mobile())
        dirCreator["Company / Works"].append("Henry Brothers")
        dirCreator["Address"].append("32 Eldon Road, Beeston, Nottingham, NG9 6DZ")
        dirCreator["Email"].append(contact.email())

    createExcel(dirCreator)

def createAddress(userXml) -> str:
    addressComb = [userXml.find("OrganizationPostalAddressLine").text,
                  userXml.find("OrganizationPostalCity").text,
                  userXml.find("OrganizationPostalState").text,
                  userXml.find("OrganizationPostalPostCode").text]

    addressComb = ", ".join(filter(None, addressComb))
    return addressComb

#Lookup person's name in my outlook contacts and return them as a Contact object
def outlooklookup(fullname : str, lastname : str, company : str, aconexid : str) -> OutlookContact:

    #connect to open outlook application - must be open on the machine for this to work
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNameSpace('MAPI')

    except AttributeError:
        raise AttributeError("Could not run. Outlook is not open and contacts could not be accessed.")

    contactsfolder = outlook.GetDefaultFolder(10)
    mycontacts = contactsfolder.Items
    lastname = lastname.replace("'","_") #wildcard any apostrophes

    #different filters to perform to try to match to outlook contacts
    sfilters = ["@SQL=""urn:schemas:contacts:governmentid"" = \'{aid}\'".format(aid = aconexid),
                "[FullName] = {f}".format(f=fullname),
                "@SQL=""urn:schemas:contacts:o"" = \'{c}\' AND ""urn:schemas:contacts:fileas"" LIKE \'%{l}\'".format(c=company,
                                                                                                       l=lastname) #TODO we need to check this one as it may return wrong results
                ]
    return filtercontacts(mycontacts, sfilters, aconexid)

def filtercontacts(mycontacts, sfilters, aconexid) -> OutlookContact:
    filteredcontacts = []
    print(sfilters)
    index = 0
    while len(filteredcontacts) == 0 and index < len(sfilters):
        filteredcontacts = mycontacts.Restrict(sfilters[index])
        index += 1

    # no match with outlook
    if len(filteredcontacts) == 0:
        return OutlookContact(None, None)
    elif len(filteredcontacts) > 1:
        config.logger.info("Matched on %s" % sfilters[index - 1])
        if index < len(sfilters):
            return filtercontacts(filteredcontacts, sfilters[index:], aconexid)
        else:  # GIVE UP
            config.logger.warning("Multiple matches found. Picking the first...")
            return OutlookContact(filteredcontacts[0], aconexid)

    else:  # one item
        config.logger.info("Matched on %s" % sfilters[index - 1])
        return OutlookContact(filteredcontacts[0], aconexid)

def createExcel(dirCreator : dict):
    fname = FOLDERPATH + "\\" + config.project().projectCodePrefix() + "Project Directory.xlsx"
    dataframe = pandas.DataFrame(data=dirCreator)
    writer = pandas.ExcelWriter(fname, mode='w', engine='xlsxwriter')
    dataframe.to_excel(writer,
                       sheet_name="Subcontractors",
                       header=True,
                       startrow=0,
                       index=False)  # no index col

    workbook = writer.book
    worksheet = writer.sheets["Subcontractors"]

    mobformat = workbook.add_format({"num_format": "0%"})
    wrapformat = workbook.add_format({'text_wrap': True})
    worksheet.set_column('D:D', None, cell_format=mobformat)
    worksheet.set_column('A:E', None, cell_format=wrapformat)

    writer.close()
    config.info("Project directory file created")

def main():
    ##Get the users to search for using the input text file
    EMAILREGEX = r"\S+@\S+\.\S+"
    USERLINEREGEX = r"(.*)<(\S+@\S+\.\S+)>" #I want: Name <email>



    file = open(FOLDERPATH + "\\userList.txt", "r")
    textLines = [line.rstrip() for line in file]
    textLines = textLines[1::] #remove top info line
    file.close

    valid = True #if all the inputs are valid
    userData = []
    skippedusers = []

    global csvOrgAdminList
    csvOrgAdminList = loadcsv()

    datenow = datetime.datetime.now(datetime.timezone.utc)
    strdatenow = datenow.strftime("%d/%m/%Y")

    for iLine in textLines:
        lineSearchRes = re.search(USERLINEREGEX, iLine)
        if lineSearchRes:
            names = lineSearchRes.group(1).strip().split(" ")
            email = lineSearchRes.group(2)
            config.info("Searching on email address %s..." % email)
            parameters = {"email": email,
                        "show_groups": "false"} #don't return mailing groups it breaks it

            tempname = parameters["email"]
            nuTracker["User"].append(iLine)

        else: #a name rather than an email
            names = iLine.split(" ") #split forename / surname
            surname = names[-1] #last val
            forename = " ".join(names[:-1])
            config.info("Searching on forename %s, surname %s..." % (forename, surname))
            parameters = {"given_name": forename,
                          "family_name": surname,
                          "show_groups": "false"} #don't return mailing groups it breaks it
            tempname = names
            nuTracker["User"].append(tempname) #ideally want it formatted correctly so don't want this to be happening

        nuTracker["Date Started"].append(strdatenow)
        nuTracker["Project"].append(config.project().projectName())

        #Search for this user on the project
        userXML = projectDirectorySearch(parameters)

        #user found on project
        if userXML != None:
            config.info("User has been found on %s" % config.project().projectName())
            nuTracker["Company"].append(userXML.find('OrganizationName').text)
            nuTracker["Done?"].append("Yes")
            nuTracker["Date Completed"].append(strdatenow)

            userData.append(userXML)

        else: #user not found on this project
            config.info("User has NOT been found on %s. Searching global directory..." % config.project().projectName())

            #check the global directory to see if user exists
            surname = names[-1]  # last val
            forename = " ".join(names[:-1])

            parameters = {"given_name": forename,
                          "family_name": surname}
            searchstatus, omail = globalDirectorySearch(parameters)
            if searchstatus == "rerun":
                textLines.append(iLine) #add again, we will search for them again at the end - as they should now be added to project

            elif searchstatus == "neworg":
                omail.setTo([iLine])
                config.info("Drafting 'New organisation' email...")
                omail.draftEmail()

            elif searchstatus == "newuser":
                omail.setCC([iLine])
                omail.body = omail.body.replace("NAME", iLine)
                config.info("Drafting 'New user' email to org admins...")
                omail.draftEmail()


    if len(userData) < 1: #if no users found
        exit()

    ##Add to All Mailing Group
    confirm = input("Add all users to 'All' Mailing Group? (Y/N): ")
    if confirm.upper() == "Y" or confirm.lower() == "yes": addToAll(userData)

    ##Add to Company Mailing Group
    confirm = input("Add users to company Mailing Group? (Y/N): ")
    if confirm.upper() == "Y" or confirm.lower() == "yes": addToGroup(userData)

    ##Draft transmittal of files
    confirm = input("Draft a full transmittal to users? (Y/N): ")
    if confirm.upper() == "Y" or confirm.lower() == "yes": transmittalSent = draftTransmittal(userData)
    else: transmittalSent = False

    ##Draft Project Invite Mail
    confirm = input("Draft project invite? (Y/N): ")
    if confirm.upper() == "Y" or confirm.lower() == "yes": draftProjectInvite(userData)

    print("SUMMARY")
    print("Success on: " + "\n".join([user.find('UserName').text for user in userData]))
    print("Skipped: " + "\n".join(skippedusers))

    #updateTracker() TODO

#if not loaded already, load csv
def loadcsv() -> dict:
    csvOrgAdminList : dict[str: (str, [str], datetime.date)] #ID: [name, admins
    csvfile = open(CSVPATH, "r", newline='')
    reader = csv.reader(csvfile, delimiter=',')
    next(reader)  # skip header row

    csvOrgAdminList = {}
    for row in reader:
        companyname = row[1]

        orgadminsRaw = row[2]
        orgadminsRaw.replace("""""", "")
        orgAdmins = str.split(orgadminsRaw, "; ")

        datestr = row[3]
        datechecked = datetime.datetime.strptime(datestr, "%d/%m/%Y")

        csvOrgAdminList[row[0]] = (companyname, orgAdmins, datechecked)

    config.logger.info("Loaded csv file")
    return csvOrgAdminList


#TODO update new user tracker with new rows
def updateTracker():
    nuTracker = {
        "User": ["Max Rebo"],
        "Company": ["Test Company"],
        "Project": ["HBP - HB Practice Project"],
        "Org Admin(s)": [""],
        "Done?": ["Yes"],
        "Action with": [""],
        "Comments": [""],
        "Date Started": ["13/08/2025"],
        "Date Completed": ["13/08/2025"]
    }
    dataframe = pandas.DataFrame(data=nuTracker)

    readerdf = pandas.read_excel(NUTRACKERPATH, sheet_name="Tracker")
    numRows = len(readerdf.index)

    writer = pandas.ExcelWriter(NUTRACKERPATH, mode='a', if_sheet_exists="overlay")

    dataframe.to_excel(writer,
                       sheet_name="Tracker",
                       header=False,
                       startrow=(numRows+1),
                       index=False)

    writer.close()