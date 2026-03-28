import json
import requests

import re #for parsing structure
import random
import string

import requests_cache
from Setup.APIcommon import getAPIResponse, putAPIResponse, jprint, postAPIResponse, putNoteInFirstQuestion


def jprint(obj):
    # create a formatted string of the Python JSON object
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)

#map of how the different templates should have their titles formatted
titleStructuresMap = {
    "Permit to Dig": "[template_title] - [Company] ([Work Description])",
    "Hotworks Permit": "[template_title] - [Company] ([Work Description])",
    "Environmental Weekly Check": "[template_title] - w/c [Week Commencing:]",
    "Permit to Dig - PDF Version": "[template_title] - [Company] ([WorkLocDesc])",
    "Hot Works Permit - PDF Form": "[template_title] - [Company] ([WorkLocDesc])"
}

session = requests_cache.CachedSession('test', expire_after=60)

def main(passedBearer, env):
    global bearer
    bearer = passedBearer
    global aconexEnv
    aconexEnv = env

    #use HB Test 1 as an example project
    global chosenProjectID
    chosenProjectID = "1879048648"
    global PROJECTURL
    PROJECTURL = aconexEnv + "/field-management/api/projects/" + chosenProjectID  # field api urls are built around the env url

    random.seed(a=int(chosenProjectID))

    areaID = "271341877549073131"  # test on this area (Site)
    url = PROJECTURL + "/areas/" + areaID + "/checklists?include_child_areas=true"  # get all inspections in this area
    headers = {'Authorization': bearer,
               'Accept': 'application/json'} #all the responses are in json format

    response = getAPIResponse(url, headers, "getting the Field inspections")
    jsonResponse = json.loads(response)

    for checklistJson in jsonResponse["checklists"]:
        checklistId: str = checklistJson["id"]
        currentStatus: str = checklistJson["status"]
        structure = getNewInspectionTitle(checklistJson)

        if structure is not None and structure != checklistJson["title"]:
            checklistJson["items"], checklistJson["groups"] = putNoteInFirstQuestion(checklistJson)

            url = aconexEnv + '/field-management/api/checklists/' + checklistId
            body = {"id": checklistJson["id"],
                    "title": structure,
                    # to add the note:
                    "items": checklistJson["items"],
                    "groups": checklistJson["groups"]
                    }
            putAPIResponse(url, headers, body, "updating the Checklist's title")

            body = {"status": currentStatus}  # status auto-opens, close it if needed
            putAPIResponse(url, headers, body, "updating the Checklist's status")

def getNewInspectionTitle(checklistJson):
    templateTitle: str = checklistJson["template_title"]
    structure, fields = findStructure(templateTitle)
    if structure is None:
        print("No structure set up for template %s." % templateTitle)
        return #skip

    descResponses: dict = {itemArr["description"]: itemArr["response"] for g in checklistJson['groups'] for itemArr in
                           g['items']}  # add items in groups
    descResponses.update({itemArr["description"]: itemArr["response"] for itemArr in
                          checklistJson['items']})  # add items that aren't in groups

    for fieldname in fields:
        if fieldname == "template_title":
            val = templateTitle
        else:
            val = shorten(descResponses[fieldname]['value']) if descResponses[fieldname] is not None else ""

        structure = structure.replace('[' + fieldname + ']', val)

    return structure.strip()


def findStructure(templateTitle: str) -> (str, [str]):
    try:
        struct = titleStructuresMap[templateTitle]
        fields = re.findall(r'\[(.*?)\]', struct)
        return struct, fields
    except KeyError:
        return None, None

def shorten(val: str):
    words = val.split(' ')
    while len(val) > 36:
        words.pop()
        val = ' '.join(words) + "..."

    return val