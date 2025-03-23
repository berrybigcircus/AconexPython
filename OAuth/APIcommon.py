import json
import requests
import pickle
import datetime
from base64 import b64encode

import requests_cache
session = requests_cache.CachedSession('test', expire_after=60)

#For setting up
def basic_auth(username, password):
    token = b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def jprint(obj):
    # create a formatted string of the Python JSON object
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)

#API Requests
def getAPIResponse(url, headers, explanation) -> str:
    response = session.get(url, headers=headers)

    #validate get request
    if response.status_code != 200:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))
        return None
    return response.text

def putAPIResponse(url, headers, body, explanation):
    response = session.put(url, headers=headers, json=body)

    # validate request
    if response.status_code != 200:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))
    else:
        print(response.status_code)
    print(response.text)

def postAPIResponse(url, headers, body, explanation) -> str:
    response = session.post(url, headers=headers, json=body)

    # validate request
    if response.status_code != 200:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))
    else:
        print(response.status_code)

    return response.text

#Specific functions
def convertDateTime(dateResponseRaw : str, format : str) -> str:
    if dateResponseRaw:
        date = datetime.datetime.strptime(dateResponseRaw, "%Y-%m-%dT%H:%M:%S.%fZ")
        return datetime.datetime.strftime(date, format)

    else:
        return ""

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

class Project():
    def __init__(self, pname: str, pID: str, pCode: str = None):
        self.__projectname = pname
        self.__projectID = pID
        self.__projectCode = pCode

    def getProject(self) -> (str, str):
        return self.__projectname, self.__projectID

    def projectCodePrefix(self) -> str:
        if self.__projectCode:
            return self.__projectCode + " - "
        else:
            return ""

def projectSelection(debug: bool = False) -> Project:
    ##Ask for project
    try:
        fp = open("../getAllProjects/projectList.txt", "rb")  # load stored projects
        projectsList = pickle.load(fp)  # load as project dictionary
        fp.close()
    except IOError:
        print("Error loading project list.")
        exit()

    print("CURRENT PROJECTS:")
    for i, (pName, pID) in enumerate(projectsList.items()):  # print projects to user
        print("    %d - %s (%s)" % (i, pName, pID))

    confirm = "n"
    projectname : str
    chosenProjectID : str

    if debug == True:
        projectname = "HB Test"
        chosenProjectID = "1879048648"
        confirm = "Y"

    while confirm.upper() != "Y" and confirm.lower() != "yes":
        projectIndex = indexInput(len(projectsList) - 1)
        print("Project - %s" % list(projectsList)[projectIndex])

        confirm = input("Confirm (Y/N):")
        chosenProjectID = list(projectsList.values())[projectIndex]
        projectname = list(projectsList)[projectIndex]

    return Project(projectname, chosenProjectID)


def putNoteInFirstQuestion(checklistJson, duplicateID=""): #put the id as a note in the first question of the inspection
    uniqueID: str = checklistJson["id"]
    firstItem : dict = {}
    isGroup: bool = False #whether in a group or not

    if len(checklistJson["items"]):
        firstItem = next(filter(lambda x: x["item_number"] == "1", checklistJson["items"]), None)
        isGroup = False
    if not firstItem:
        firstItem = [x for itemJson in checklistJson["groups"] for x in itemJson["items"] if x["item_number"] == "1"][0]
        isGroup = True

    assert firstItem

    # if not firstItem["response"]:
    #     return [], [] #add no comment if first box is empty

    currentComment = firstItem["note"]["comment"] + "\n" if firstItem["note"] else ""
    id = firstItem["id"]
    firstItem.clear()
    firstItem["id"] = id

    firstItem["comment"] = currentComment + "Unique ID: " + uniqueID #add ID to the note text
    if duplicateID != "": #if this checklist is a duplicate, add this into the comment as well
        firstItem["comment"] = firstItem["comment"] + "\nDuplicate of " + duplicateID

    if isGroup:
        groupJson = [{"id": checklistJson["groups"][0]["id"],
                     "items": firstItem}]

        return [], groupJson
    else:
        return firstItem, []