from OAuth.APIcommon import getAPIResponse, putAPIResponse, postAPIResponse, jprint, putNoteInFirstQuestion
import json
from inspectionRenamer import getNewInspectionTitle

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
    areaId = json.loads(response)["areas"][0]["id"] #root area id is the first one returned (can search all checklists from the root)

    searchFor = str(input("Enter checklist-id or title of field inspection to duplicate: ")) #DEBUG "407d0de7-a365-493a-bf51-c64232de224c"
    #TODO - deal with 100+ results
    if len(searchFor.split('-'))==5: #assume a checklist id was entered if it's four dashes
        print("Searching for checklist ID %s across all areas ..." % searchFor)
        url = PROJECTURL + '/areas/' + areaId + '/checklists/' + searchFor
    elif searchFor == "*" or searchFor == "": #search all
        print("Returning all checklists...")
        url = PROJECTURL + '/areas/' + areaId + '/checklists?include_child_areas=true'
    else:
        print("Searching for inspections with '%s' in title across all areas..." % searchFor)
        url = PROJECTURL + '/areas/' + areaId + '/checklists?include_child_areas=true&title=' + searchFor

    response = getAPIResponse(url, headers, "searching for the field checklist")
    jsonResponse = json.loads(response)

    if not "total_results" in jsonResponse.keys(): #id search
        chosenChecklist = jsonResponse
    elif jsonResponse["total_results"] > 1:
        items = {}
        for i, checklistJson in enumerate(jsonResponse["checklists"]):
            items[checklistJson["number"]] = checklistJson
            inUrl = aconexEnv + "/field/app/headless/#/projects/{pId}/edit-inspection?areaId={aId}&checklistId={cId}&checklistAreaId={caId}".format(pId=chosenProjectID, aId=areaId, cId=checklistJson["id"], caId=checklistJson["area"]["id"])
            print("Item Number %s: %s (%s)" % (checklistJson["number"], checklistJson["title"], inUrl))

        itemNumInput = str(input("Enter item number: "))
        while itemNumInput not in items.keys():
            itemNumInput = str(input("Enter item number: "))

        chosenChecklist = items[itemNumInput]
    elif jsonResponse["total_results"] == 1:
        chosenChecklist = jsonResponse["checklists"][0]

    else: #no results
        print("No results found.")
        exit()

    print("Duplicating %s..." % chosenChecklist["title"])
    chosenChecklist["status"] = "open" #it is open

    chosenChecklist["description"] = "Duplicate of '{}'".format(chosenChecklist["title"])

    newTitle = getNewInspectionTitle(chosenChecklist) #from inspectionRenamer, create a new title
    chosenChecklist["title"] = newTitle if newTitle is not None else chosenChecklist["template_title"]


    #first, create a new checklist
    url = PROJECTURL + '/areas/' + areaId + "/checklists"
    body = {
        "title": chosenChecklist["title"],
        "organization": chosenChecklist["organization"],
        "project": chosenChecklist["project"],
        "area": chosenChecklist["area"],
        "status": "open",
        "template_url": chosenChecklist["template_url"],
    }
    # createdChecklist = json.loads(getAPIResponse(url=PROJECTURL + '/areas/' + areaId + '/checklists/' + "414b5d0c-7c55-4da3-8ae1-73d24fe01480",
    #                                              headers=headers,
    #                                              explanation=""))
    createdChecklist = json.loads(postAPIResponse(url, headers, body, "creating the new checklist"))
    newId = createdChecklist["id"]

    createdChecklist["items"], createdChecklist["groups"] = cleanItems(chosenChecklist, createdChecklist)

    #update the newly created checklist with the question responses
    url = aconexEnv + '/field-management/api/checklists/' + newId
    print(createdChecklist["items"])
    body = {
        "items": createdChecklist["items"],
        "groups": createdChecklist["groups"],
        # "groups": [{
        #     "id": "bc76e777-40a7-4fc3-986e-08e79a476bd2",
        #     "items": [
        #         {
        #             "id": "f99e1965-3462-4689-85ba-1a0c9de096c9",
        #             "response": {"value": "Company B"}
        #         }
        #     ]
        # }]
    }
    putAPIResponse(url, headers, body, "updating the new checklist")


def extractJson(jsonS, layers):
    for key, layer in layers.items():
        if not jsonS: #nothing
            return None
        if not layer:
            items = []
            finalDict = {}
            for dict in jsonS:
                items.append(dict[key])
            finalDict[key] = items
            return finalDict

        for item in layer:
            newItems = []
            finalDict = {}
            for dict in jsonS:
                extracted = extractJson(dict[key], item)
                if extracted: newItems.append(extracted)
            finalDict[key] = newItems


def cleanItems(ogChecklist, createdChecklist):
    layers = {
        "items": [{
                "id": None,
                "response": {"value": None}
        }],
        "groups": [{
            "id": None,
            "items": [{
                "id": None,
                "response": {"value": None}
            }]
        }]
    }

    finalChecklist = {}
    finalItems = []
    for i, itemJson in enumerate(ogChecklist["items"]):
        finalDict = {}
        finalDict["id"] = createdChecklist["items"][i]["id"] #use the ID number from the newly created checklist. this is in case the template was updated slightly and the IDs are now different
        finalDict["response"] = {}
        finalDict["response"]["value"] = itemJson["response"]["value"]
        finalItems.append(finalDict)

    finalChecklist["items"] = finalItems

    fGroups = []
    for i, groupJson in  enumerate(ogChecklist["groups"]):
        eachGroup = {}
        eachGroup["id"] = createdChecklist["groups"][i]["id"] #the group id
        finalItems = []
        for j, itemJson in enumerate(groupJson["items"]):
            finalDict = {}
            finalDict["id"] = createdChecklist["groups"][i]["items"][j]["id"]
            finalDict["response"] = {}
            finalDict["response"]["value"] = itemJson["response"]["value"]
            finalItems.append(finalDict)

        eachGroup["items"] = finalItems
        fGroups.append(eachGroup)

    finalChecklist["groups"] = fGroups

    # add comment to first checklist item with a new random id, and that it is a duplicate
    tempItems, tempGroups = putNoteInFirstQuestion(createdChecklist, ogChecklist["id"])

    return finalChecklist["items"], finalChecklist["groups"]

    #newChecklist = extractJson(newChecklist, layers)


def removeIssuesAttachments(newChecklist):
    #TODO
    return newChecklist

def removeSignatures(newChecklist):
    #"type": "signature"

    #remove signatures that aren't in a group


    #remove signatures that are in a group
    return newChecklist

def removeDates(newChecklist):
    #TODO
    return newChecklist