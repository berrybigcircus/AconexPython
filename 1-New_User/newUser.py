import csv
import time

import requests #for making http requests
import json #for reading json
from urllib.parse import urlencode, quote_plus
import xml.etree.ElementTree as ET #for parsing xml
import re #regex
import webbrowser
import datetime
import pandas

from OAuth.APIcommon import session, getAPIResponse, postAPIResponse, indexInput
from OAuth.MailClasses import getProjectInviteMailID
import OAuth.config as config

ORGFILTERENDS = ["Ltd", "Limited", "LLC", "Inc", "Pty", "Pte", "Pvt", "Consulting", "(midlands)", "Architects"]  # remove these from the organisation name when creating/searching for company mailing group
ORGFILTERSTARTS = ["The"]

CSVPATH = r"C:\Users\nicole.millinship\OneDrive - Henry Brothers Ltd\CLP - Docs\General\#Other Files\Aconex\OrgAdminList.csv"

NUTRACKERPATH = r"C:\Users\nicole.millinship\OneDrive - Henry Brothers Ltd\CLP - Docs\General\#Other Files\Aconex\Aconex New Users Tracker - Copy.xlsx"
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

def searchForCompany(companyname, usersFilter):
    parameters = {"org_name": companyname}
    url = config.env() + "/api/directory?" + urlencode(parameters)
    return directorySearch(url, usersFilter, False)

def globalDirectorySearch(parameters: dict) -> str:
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
            #TODO Send 'new org email'
            print("Drafting 'New organisation' email...")
            nuTracker["Company"].append(companyname) #you may need to edit later
            nuTracker["Action with"].append("User")
            nuTracker["Comments"].append("New org")
            return "neworg"

        orgadmins : list[str] = None
        datechecked : datetime.datetime = None

        # look up org name in csv to find org admins
        orgadmins, datechecked = csvOrgAdminList.get(orgname) or (None, None)

        #no data in csv or last checked too long ago
        while orgadmins is None or datechecked < (datetime.datetime.today() - datetime.timedelta(days=DAYSLIMIT)):
            #Find out the org admin(s)
            # there is no api request for org admins, but the xml is available on the web
            url = config.env() + "/internal/projects/" + config.project().projectID() + "/organizations/" + orgid + "/orgAdmins"
            print(url)
            file = open("orgadminheader.txt",
                        "r")  # here i have saved the headers i got via inspect element - not sure how well this will continue to work
            headers = dict(line.split(': ', 1) for line in file.read().splitlines())
            file.close()

            jsonRes = getAPIResponse(url, headers, "getting the org admins. Cookies may need to be redone")
            if jsonRes is None:
                return "Error"

            orgadmins = parseOrgAdmins(json.loads(jsonRes))

            if orgadmins is None:
                orgid, orgname = searchForCompany(companyname, usersFilter)

            datechecked = datetime.datetime.now()

        updateOrgAdminCSV(orgname, orgadmins, datechecked)
        print("Drafting email to org admins - " + orgadmins) #TODO

        nuTracker["Action with"].append("Org admin")
        nuTracker["Comments"].append("New user")

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
        return "rerun"

def updateOrgAdminCSV(orgname : str, orgadmins : list[str], datechecked : datetime):
    strdateChecked = datechecked.strftime("%d/%m/%Y")
    combOrgAdmins = "; ".join(orgadmins)
    newRow = [orgname, combOrgAdmins, strdateChecked]

    #if this org was already in the csv
    if orgname in csvOrgAdminList.keys():
        #we will have to rewrite the whole csv, no other way with csv files
        csvOrgAdminList[orgname] = (orgadmins, datechecked)

        rows = [[k, "; ".join(v[0]), v[1].strftime("%d/%m/%Y")] for k, v in csvOrgAdminList.items()]

        csvfile = open(CSVPATH, 'w', newline='')
        writer = csv.writer(csvfile, delimiter = ',')
        writer.writerow(["Company", "Org Admin(s)", "Date Checked"]) #put header in
        writer.writerows(rows)
    else:
        csvfile = open(CSVPATH,'a', newline='')
        writer = csv.writer(csvfile, delimiter = ',')
        writer.writerow(newRow)
        csvfile.close()
        csvOrgAdminList[orgname] = (orgadmins, datechecked)

#convert xml to a list of org admin names/emails separated by ;
def parseOrgAdmins(jsonRes) -> list[str] | None:
    oaArr = jsonRes["orgAdmins"]
    orgAdminList = [(oa['name'] + " <" + oa['email'] + ">") for oa in oaArr]
    print("Org admins found: " + ",".join(orgAdminList))
    inputCheck = input("Look okay? (Y/N): ")
    if inputCheck.upper() != "Y":
        return None
    else:
        return orgAdminList

def projectDirectorySearch(parameters):
    url = config.projecturl() + "/directory?" + urlencode(parameters)
    chosenUser, _ = directorySearch(url, "SearchResults/Directory", True)

    isHB = chosenUser.find("OrganizationName").text == "Henry Brothers" if chosenUser else False
    if isHB:  # if they are in henry brothers, add to HB confidential as well
        groupid, _ = findMailingGroup(getMailingGroups(),"HB Confidential")
        statuscode, reason = addUserstoMG(groupid,[chosenUser.find("UserId").text])
        if statuscode == 200:
            print("Henry Brothers user added to HB Confidential.")
        else:
            print("There was an error adding HB user to HB Confidential. " + reason)

    return chosenUser

def directorySearch(url, searchfilter, userSearch=True) -> tuple[ET.Element | None | str, None | str]:
    headers = {'Authorization': config.bearer()}
    xml = getAPIResponse(url, headers, "searching the directory")
    root = ET.fromstring(xml)
    numFound = int(root.attrib['TotalResults'])
    print(xml)
    if numFound == 0:
        print("No %s found with those details." % ("users" if userSearch else "orgs"))
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


def getMailingGroups():
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

def createMailingGroup(groupName):
    url = config.env() + "/api/mailinggroups/" + config.project().projectID()
    headers = {'Authorization': config.bearer()}
    #Create All mailing group
    jsonData = {"groups": [{
        "groupName": groupName,
        "isLocked": "false"
        }]}
    response = postAPIResponse(url=url, headers=headers, body=jsonData, explanation="creating mailing group")

    print("'%s' mailing group created." % groupName)
    session.cache.clear()
    mgResponse = getAPIResponse(url, headers, "finding mailing groups") #it doesn't return the id of the new group, so have to run the get again
    jsonMG = json.loads(mgResponse)

    searchTerm = "^" + groupName + "$" #should be able to search exact for any mailing group as it was just created with this name
    return findMailingGroup(jsonMG, searchTerm)

def addToAll(userData):
    #check for existence of All group
    jsonMG = getMailingGroups()
    
    mgID, mgUsers = findMailingGroup(jsonMG, "^All$")

    if mgID == 0: #'All' not found
        mgID, mgUsers = createMailingGroup("All")

    usersToAdd = [dirUser.find("UserId").text for dirUser in userData if int(dirUser.find("UserId").text) not in mgUsers] #list the user ID of users not already in the mailing group

    if len(usersToAdd) == 0:
        print ("The users are in the 'All' mailing group already.")
        return

    #Add to 'All'
    statuscode, reason = addUserstoMG(mgID, usersToAdd)

    if statuscode != 200:
        print("There was an error adding the users to the 'All' mailing group. %s" % reason)
    else:
        print("Users added to 'All' mailing group successfully.")

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
    jsonMG = getMailingGroups()

    for dirUser in userData: #must check each user's org
        userName = dirUser.find("UserName").text
        userID = int(dirUser.find("UserId").text)


        orgName = dirUser.find("TradingName").text #trading name is what displays on the directory
        filteredOrgName = cleanOrgName(orgName)
        regSearch = ".*" + filteredOrgName + ".*"
        mgID, mgUsers = findMailingGroup(jsonMG, regSearch)

        if mgID == 0: #Group not found
            mgID, mgUsers = createMailingGroup(filteredOrgName)
            session.cache.clear()
            jsonMG = getMailingGroups() #need to refresh MG list

        if userID not in mgUsers:
            statuscode, reason = addUserstoMG(mgID, [userID])

            if statuscode != 200:
                print("There was an error adding user %s to the mailing group. %s" % (userName, reason))
            else:
                print("User %s added to mailing group successfully." % userName)
        
        else:
            print("User %s is already in the mailing group." % userName)

def cleanOrgName(orgName : str) -> str:
    orgWords = orgName.split(" ")  # split into words
    orgWords = orgWords if orgWords[0] not in ORGFILTERSTARTS else orgWords[1:]
    while orgWords[-1] in ORGFILTERENDS:
        orgWords = orgWords[:-1]
    return " ".join(orgWords)

def draftTransmittal(userData):
    #get HBDC All Docs
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

    xmlFile = open("xmlFiles/allTransmittal.xml", "r")
    xmlData = xmlFile.read()
    xmlFile.close()

    xmlData = xmlData.replace("ATTACHMENT_COUNT_GOES_HERE",str(len(docIds)))

    xmlData = addUsersAndDocs(xmlData, userIds, docIds)

    response = requests.post(url, headers=headers, data=xmlData)

    if response.status_code != 200:
        print("There was an error in drafting the transmittal. %s" % response.reason)
        return False

    returnedXml = response.text
    draftedMailId = ET.fromstring(returnedXml.strip()).find('NewMailId').text

    draftMailURL = config.env() + "/rsrc/20250422.1347/en_AU_DOC/mail/view/index.html#/" + config.project().projectID() + "/" + draftedMailId
    print ("Draft transmittal created. Opening link...")
    webbrowser.open(draftMailURL)

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
        print("There was an error getting data about the draft mail. %s" % response.reason)
        return
    
    #create mail
    url = config.projecturl() + "/mail?is_draft=true"
    headers = {'Authorization': config.bearer(),
                'Content-Type': 'multipart/mixed',
                'boundary': 'myboundary'}

    docCount = chosenInviteMail.find('AttachedDocumentCount').text

    xmlFile = open("xmlFiles/inviteMail.xml", "r")
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
        print("There was an error drafting the project invite mail. %s" % response.reason)
        return

    returnedXml = response.text
    draftedMailId = ET.fromstring(returnedXml.strip()).find('NewMailId').text

    draftMailURL = config.env() + "/rsrc/20250422.1347/en_AU_DOC/mail/view/index.html#/" + config.project().projectID() + "/" + draftedMailId
    print("Draft project invite created. Opening link...")
    webbrowser.open(draftMailURL)

dirCreator = { #headings for csv for project directory
    "Name": [],
    "Company / Works": [],
    "Role": [],
    "Contact Number": [],
    "Address": []
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
                    print(orgaddress)
                except StopIteration: #at end of list
                    break
                if orgaddress != "":
                    break

            for userXml in searchXml:

                dirCreator["Name"].append(userXml.find("UserFirstName").text.title() + " " + userXml.find("UserLastName").text.title())
                dirCreator["Role"].append(userXml.find("JobTitle").text)
                contactnum = userXml.find("Mobile").text or userXml.find("Phone").text
                dirCreator["Contact Number"].append(contactnum)
                dirCreator["Company / Works"].append(groupname)
                dirCreator["Address"].append(orgaddress)

    createExcel(dirCreator)

def createAddress(userXml) -> str:
    addressComb = [userXml.find("OrganizationPostalAddressLine").text,
                  userXml.find("OrganizationPostalCity").text,
                  userXml.find("OrganizationPostalState").text,
                  userXml.find("OrganizationPostalPostCode").text]

    addressComb = ", ".join(filter(None, addressComb))
    return addressComb

def createExcel(dirCreator : dict):
    fname = config.project().projectCodePrefix() + "Project Directory.xlsx"
    dataframe = pandas.DataFrame(data=dirCreator)
    writer = pandas.ExcelWriter(fname, mode='w')
    dataframe.to_excel(writer,
                       sheet_name="Subcontractors",
                       header=True,
                       startrow=0,
                       index=False)  # no index col
    writer.close()
    print("Project directory file created")

def main():
    ##Get the users to search for using the input text file
    EMAILREGEX = r"\S+@\S+\.\S+"
    USERLINEREGEX = r"(.*)<(\S+@\S+\.\S+)>" #I want: Name <email>

    file = open("userList.txt", "r")
    textLines = [line.rstrip() for line in file]
    textLines = textLines[1::] #remove top info line
    file.close

    valid = True #if all the inputs are valid
    userData = []
    skippedusers = []
    global csvOrgAdminList
    csvOrgAdminList = loadcsv()

    updateOrgAdminCSV("Test Company", ["Sy Snootles <snootie@snoop.com>", "Max Rebo <max@rebo.com>"], datetime.datetime.now()) #test

    datenow = datetime.datetime.now(datetime.timezone.utc)
    strdatenow = datenow.strftime("%d/%m/%Y")

    for iLine in textLines:
        lineSearchRes = re.search(USERLINEREGEX, iLine)
        if lineSearchRes:
            names = lineSearchRes.group(1).strip().split(" ")
            email = lineSearchRes.group(2)
            print("Searching on email address %s..." % email)
            parameters = {"email": email,
                        "show_groups": "false"} #don't return mailing groups it breaks it

            tempname = parameters["email"]
            nuTracker["User"].append(iLine)

        else: #a name rather than an email
            print("Invalid format, treating %s as a name" % iLine)
            names = iLine.split(" ") #split forename / surname
            surname = names[-1] #last val
            forename = " ".join(names[:-1])
            print("Searching on forename %s, surname %s..." % (forename, surname))
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
            print("User has been found on %s" % config.project().projectName())
            nuTracker["Company"].append(userXML.find('OrganizationName').text)
            nuTracker["Done?"].append("Yes")
            nuTracker["Date Completed"].append(strdatenow)

            userData.append(userXML)

        else: #user not found on this project
            print("User has NOT been found on %s. Searching global directory..." % config.project().projectName())
            #check the global directory to see if user exists
            surname = names[-1]  # last val
            forename = " ".join(names[:-1])
            print(names)
            parameters = {"given_name": forename,
                          "family_name": surname}
            searchstatus = globalDirectorySearch(parameters)
            if searchstatus == "rerun":
                textLines.append(iLine) #add again, we will search for them again at the end - as they should now be added to project

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

    updateTracker()

#if not loaded already, load csv
def loadcsv() -> dict:
    csvOrgAdminList : dict[str: ([str], datetime.date)]
    csvfile = open(CSVPATH, "r", newline='')
    reader = csv.reader(csvfile, delimiter=',')
    next(reader)  # skip header row

    csvOrgAdminList = {}
    for row in reader:
        orgadminsRaw = row[1]
        orgadminsRaw.replace("""""", "")
        orgAdmins = str.split(orgadminsRaw, "; ")

        datestr = row[2]
        datechecked = datetime.datetime.strptime(datestr, "%d/%m/%Y")

        csvOrgAdminList[row[0]] = (orgAdmins, datechecked)

    return csvOrgAdminList


#update new user tracker with new rows
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