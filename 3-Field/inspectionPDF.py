from OAuth.APIcommon import getAPIResponse, putAPIResponse, postAPIResponse, jprint, putNoteInFirstQuestion
import json

def main(passedBearer, env):
    global bearer
    bearer = passedBearer
    global aconexEnv
    aconexEnv = env

    # use HB Test 1 as an example project
    global chosenProjectID
    chosenProjectID = "1879048648"
    global PROJECTURL
    PROJECTURL = aconexEnv + "/field-management/api/projects/" + chosenProjectID  # field api urls are built around the env url


    url = PROJECTURL + "/areas" #get all areas
    headers = {'Authorization': bearer,
               'Accept': 'application/json'}

    response = getAPIResponse(url, headers, "getting the Field areas for this project")
    areaID = "271341877549073131" # test on this area (Site)
    searchFor = "7a271d56-b441-4503-b066-c8ee40e8f3c9"

    url = PROJECTURL + '/areas/' + areaID + '/checklists/' + searchFor
    headers = {'Authorization': bearer,
               'Accept': 'application/json'} #all the responses are in json format

    response = getAPIResponse(url, headers, "searching for the field checklist")
    checklistJson = json.loads(response)

    #Get the template metadate
    url = aconexEnv + checklistJson["template_url"]
    response = getAPIResponse(url, headers, "searching for the field's template data")
    jsonResponse = json.loads(response)
    isPdfForm : bool = jsonResponse["isPdfForm"]

    checklistId: str = checklistJson["id"]

    #if a normal checklist, not a pdf form
    if not isPdfForm:
        checklistJson["items"], checklistJson["groups"] = putNoteInFirstQuestion(checklistJson)

    else:
        checklistJson["items"] = addUniqueID(checklistJson)
        checklistJson["groups"] = [] #leave groups blank (there's no groups on pdf forms)

    url = aconexEnv + '/field-management/api/checklists/' + checklistId
    body = {"id": checklistJson["id"],
            # to add the note:
            "items": checklistJson["items"],
            "groups": checklistJson["groups"]
            }
    putAPIResponse(url, headers, body, "updating the Checklist's ID record")

 #why does it not work? it looks good, but doesn't wokr :(
 #IT is Oracle's fault, the PDF is not updating
def addUniqueID(checklistJson, duplicateID=""):
    uniqueID: str = checklistJson["id"]

    # find the question in the pdf form asking for the unique id
    index, idQuestion = findIDQuestion(checklistJson)
    print(idQuestion)
    if not idQuestion["response"]: idQuestion["response"] = {}
    idQuestion["response"]["value"] = uniqueID
    if duplicateID != "":  # if this checklist is a duplicate, add this into the comment as well
        idQuestion["response"]["value"] += " (Duplicate of " + duplicateID + ")"

    #just take the ID and response fields, only fields required for put request
    temp = {"id": idQuestion["id"], "response": {'value': idQuestion["response"]["value"]}}

    print(temp)
    return [temp]



def findIDQuestion(checklistJson):
    for i, itemJson in enumerate(checklistJson["items"]):
        if itemJson["description"] == "checklistID":
            return i, itemJson
