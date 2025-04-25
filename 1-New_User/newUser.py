import requests #for making http requests
import json #for reading json
from base64 import b64encode
from urllib.parse import urlencode
import xml.etree.ElementTree as ET #for parsing xml
import re #regex
import pickle
import webbrowser
import datetime
import pandas

from OAuth.APIcommon import projectSelection, Project, session

ORGFILTERENDS = ["Ltd", "Limited", "LLC", "Inc", "Pty", "Pte", "Pvt"]  # remove these from the organisation name when creating/searching for company mailing group
ORGFILTERSTARTS = ["The"]

##Function defs
def directorySearch(parameters):
    url = PROJECTURL + "/directory?" + urlencode(parameters)
    headers = {'Authorization': bearer}
    
    xml = getResponse(url, headers, "searching the directory")
    root = ET.fromstring(xml)

    numusersFound = int(root.attrib['TotalResults'])
    
    if numusersFound == 0:
        print("No users found on this project with those details.")
        return ""
    elif numusersFound > 1:
        print("%d results found:" % numusersFound)
        
        toFind = root.findall("SearchResults/Directory") #TODO root.findall("SearchResults/Directory[SearchResultType='GUEST_TYPE']") #list the users (don't include guests)
        for i, user in enumerate(toFind):
            print ("    %d - %s of %s" %(i, user.find('UserName').text, user.find('OrganizationName').text))

        userIndex = indexInput(len(toFind)-1)

        return toFind[userIndex]
    else:
        return root.find('SearchResults/Directory') #return singular user

def getResponse(url, headers, explanation):
    response = requests.get(url, headers=headers)

    #validate get request
    if response.status_code != 200:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))
        exit()
    return response.text

def indexInput(maxVal):
    valid = False

    while valid == False:
        userInput = input("Enter index: ")

        if not userInput.isdigit():
            print("Enter a number.")
            continue

        chosenIndex = int(userInput)
        if chosenIndex > maxVal or chosenIndex < 0:
            print("Enter a number between 0 and %d." % maxVal)
            continue

        return chosenIndex

def getMailingGroups():
    url = "https://api.aconex.com/api/mailinggroups/" + chosenProjectID #they structured the url different for no reason
    headers = {'Authorization': bearer}
    mgResponse = getResponse(url, headers, "finding mailing groups") #it returns some json garbo not xml
    jsonMG = json.loads(mgResponse)

    return jsonMG

def findMailingGroup(jsonMG, regSearch):
    #find MG from returned list of mailing groups (if it exists), using regex search term on the group name
    mailingGroups = jsonMG["mailingGroups"] #list of groups
    mgID = 0
    mgUsers = []

    if mailingGroups == None: return mgID, mgUsers
    
    for group in mailingGroups:
        if re.search(regSearch, group["groupName"]):
            mgID = group["groupId"]
            mgUsers = [user["userId"] for user in group["users"]] if group["users"] != None else [] #extract just the id 

    return mgID, mgUsers

def createMailingGroup(groupName):
    url = "https://api.aconex.com/api/mailinggroups/" + chosenProjectID
    headers = {'Authorization': bearer}
    #Create All mailing group
    jsonData = {"groups": [{
        "groupName": groupName,
        "isLocked": "false"
        }]}
    response = requests.post(url, headers=headers, json=jsonData) #use same url

    if response.status_code != 201: #if not successfully created
        print("The group %s wasn't found and there was an error creating it. %s" % (groupName, response.reason))
        exit()

    print("'%s' mailing group created." % groupName)
    mgResponse = getResponse(url, headers, "finding mailing groups") #it doesn't return the id of the new group, so have to run the get again
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
    url = "https://api.aconex.com/api/mailinggroups/" + chosenProjectID + "/addUsers"
    headers = {'Authorization': bearer}
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
        orgWords = orgName.split(" ") #split into words
        orgWords = orgWords if orgWords[0] not in ORGFILTERSTARTS else orgWords[1:]
        while orgWords[-1] in ORGFILTERENDS:
            orgWords = orgWords[:-1]
        filteredOrgName = " ".join(orgWords)
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

def draftTransmittal(userData):
    #get HBDC All Docs
    HBDCALLDOCS = "matchAll:1 confidential:0 AND NOT (SharedWith_singleSelect:Internal* OR SharedWith_singleSelect:Shared*)" #manual recreation of this search
    parameters = {"search_type": "PAGED", #PAGED, meaning return results by "pages" of variable size.
                  "return_fields": "docno,title,doctype,confidential,SharedWith_singleSelect", 
                  "search_query": HBDCALLDOCS
                  } 

    headers = {'Authorization': bearer}
    url = PROJECTURL + "/register?" + urlencode(parameters)

    response = requests.get(url, headers=headers)
    xml = response.text

    searchXml = ET.fromstring(xml.strip()).findall('SearchResults/')
    docIds = [doc.attrib['DocumentId'] for doc in searchXml]
    userIds = [dirUser.find("UserId").text for dirUser in userData]

    #draft transmittal
    url = PROJECTURL + "/mail?is_draft=true"
    headers = {'Authorization': bearer,
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

    draftMailURL = aconexEnv + "/rsrc/20250422.1347/en_AU_DOC/mail/view/index.html#/" + chosenProjectID + "/" + draftedMailId
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
              "search_query": "corrtypeid:1879048551" #get project invite mail types only
              }

    url = PROJECTURL + "/mail?" + urlencode(parameters)
    headers = {'Authorization': bearer}
    response = requests.get(url, headers=headers)
    xml = ET.fromstring(response.text.strip())

    searchXml = xml.findall('SearchResults/Mail')
    inviteTypes = [mail.find('Subject').text.split(" - ")[1] for mail in searchXml]

    #ask user to choose project invite draft type
    print("Invite types available on this project:")
    for i, inv in enumerate(inviteTypes): #output options to user
        print("    %d - %s" % (i, inv))

    chosenInviteSubj = inviteTypes[indexInput(len(inviteTypes)-1)]
    chosenInviteMail = xml.find("SearchResults/Mail[Subject='Project Invite - {}']".format(chosenInviteSubj))

    #get entire mail metadata for that project invite draft
    url = PROJECTURL + "/mail/" + chosenInviteMail.attrib['MailId'] #view mail metadata
    response = requests.get(url, headers=headers)
    draftMailXML = ET.fromstring(response.text.strip())

    if response.status_code != 200:
        print("There was an error getting data about the draft mail. %s" % response.reason)
        return
    
    #create mail
    url = PROJECTURL + "/mail?is_draft=true"
    headers = {'Authorization': bearer,
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

    draftMailURL = aconexEnv + "/rsrc/20250422.1347/en_AU_DOC/mail/view/index.html#/" + chosenProjectID + "/" + draftedMailId
    print("Draft project invite created. Opening link...")
    webbrowser.open(draftMailURL)

def main(passedBearer, env, project: Project=projectSelection()):
    global bearer
    bearer = passedBearer
    global aconexEnv
    aconexEnv = env

    global projectname
    global chosenProjectID
    projectname, chosenProjectID = project.getProject()

    global PROJECTURL
    PROJECTURL = "https://api.aconex.com/api/projects/" + chosenProjectID #url of the chosen project (using project id)

    ##Get the users to search for using the input text file
    EMAILREGEX = r"\S+@\S+\.\S+"

    file = open("userList.txt", "r")
    textLines = [line.rstrip() for line in file]
    textLines = textLines[1::] #remove top info line
    file.close

    valid = True #if all the inputs are valid
    userData = []

    for iLine in textLines:
        emailsFound = re.findall(EMAILREGEX,iLine)
        if len(emailsFound) > 1:
            print("Invalid search name %s" % iLine)
            valid = False
            break
            
        elif len(emailsFound) == 1:
          print("Searching on email address %s..." % emailsFound[0])
          parameters = {"email": emailsFound[0],
                        "show_groups": "false"} #don't return mailing groups it breaks it

        else: #a name rather than an email
            names = iLine.split(" ") #split forename / surname
            surname = names[-1] #last val
            forename = " ".join(names[:-1])
            print("Searching on forename %s, surname %s..." % (forename, surname))
            parameters = {"given_name": forename,
                          "family_name": surname,
                          "show_groups": "false"} #don't return mailing groups it breaks it

        userXML = directorySearch(parameters)
        if userXML == "":
            valid = False
            break
        else:
            userData.append(userXML)

    if valid == False: #if any of the users were invalid, end program
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

    ##TODO Update the new users tracker
    #updateTracker("HB Test", userData)

def updateTracker(projectName, userData):
    trackerDF = pandas.read_excel("Aconex Dummy New Users Tracker.xlsx", sheet_name="Tracker")

    print(trackerDF["Project"])
    userNames = [dirUser.find("UserName").text for dirUser in userData]
    print(userNames)
    #trackerDF.to_excel("Aconex Dummy New Users Tracker.xlsx", sheet_name="Tracker")