import json
import os
import pathlib
import shutil
import datetime
import mimetypes

from Setup.config import config
from Setup.APIcommon import getAPIResponse, getAPIFile, postAPIResponse, postAPIFile, putAPIResponse


def downloadFieldPhotos(issuenumber : int = None):
    global PROJECTURL
    PROJECTURL = config.env() + "/field-management/api/projects/" + config.project().projectID()  # field api urls are built around the env url

    global PATH
    PATH = str(pathlib.Path(__file__).parent.resolve()) + "\\PhotosDownloaded\\"

    headers = {'Authorization': config.bearer(),
               'Accept': 'application/json'}

    #get issue types
    PHOTOISSUEID = getPhotoIssueID()

    #check for areas
    jsonResponse = getAreasJson()
    areas = jsonResponse["areas"][0]["children"] #first level of areas
    areasToSearch = []
    #get first level of areas
    for aR in areas:
        areaId = aR["id"]
        areaName = aR["name"]

        if areaName.lower() == "no longer in use":
            continue

        areasToSearch.append((areaId, areaName))

    print(areasToSearch)

    #if specific issue number has been selected for download
    if issuenumber:
        #look up issue ID and area ID for the chosen issue number
        areaID = jsonResponse["areas"][0]["id"] #root area
        url = f"{PROJECTURL}/areas/{areaID}/issues?issue_type={PHOTOISSUEID}&issue_number={issuenumber}&include_child_areas=true"
        response = getAPIResponse(url, headers, "getting the issues in that area")
        jsonResponse = json.loads(response)
        issuesJson = list(filter(lambda j: j["attachments"] != [], jsonResponse["issues"]))
        assert(len(issuesJson) == 1)
        issue = issuesJson[0]
        foldername = parseLocation(issue["area"]["path"])
        downloadAttachments(issue["issue_id"], issue["area"]["id"], foldername)

    else:
        for areaID, areaname in areasToSearch:
            #Get all issues in area of 'Photo' type
            url = PROJECTURL + "/areas/" + areaID + "/issues?issue_type=" + PHOTOISSUEID + "&include_child_areas=true"
            response = getAPIResponse(url, headers, "getting the issues in that area")
            jsonResponse = json.loads(response)
            issuesJson = filter(lambda j: j["attachments"] != [], jsonResponse["issues"])
            for issue in issuesJson:
                foldername = parseLocation(issue["area"]["path"])
                print(foldername)
                downloadAttachments(issue["issue_id"], issue["area"]["id"], foldername)

        #Zip the photos up
        zippath = PATH + jsonResponse["areas"][0]["name"]
        shutil.make_archive(zippath, 'zip', zippath)

        print("Completed zip.")

def parseLocation(jsonPath):
    location = ""
    for loc in jsonPath:
        location += loc["name"].replace("/","&") + "\\"

    return location

def getPhotoIssueID():
    url = PROJECTURL + "/issue_types"
    headers = {'Authorization': config.bearer(),
               'Accept': 'application/json'}

    response = getAPIResponse(url, headers, "getting the issue types")
    jsonResponse = json.loads(response)
    issueTypes = jsonResponse["issue_types"]

    PHOTOISSUEID = [iType["id"] for iType in issueTypes if iType["name"] == "Photos"][0]
    return PHOTOISSUEID

def getAreasJson():
    url = PROJECTURL + "/areas"
    headers = {'Authorization': config.bearer(),
               'Accept': 'application/json'}

    response = getAPIResponse(url, headers, "getting the areas")
    return json.loads(response)

def getAreas(areas):
    areasToSearch = []
    for aR in areas:
        areaId = aR["id"]
        areaName = aR["name"]

        if areaName.lower() == "no longer in use":
            continue

        areasToSearch.append((areaId, areaName))

        areaChildren = aR["children"]

        if len(areaChildren) > 0:
            areasToSearch.append(getAreas(areaChildren))

    return areasToSearch

def downloadAttachments(issueID : str, areaid : str, folderpath : str):
    baseurl = PROJECTURL + '/areas/' + areaid + "/issues/" + issueID
    headers = {'Authorization': config.bearer(),
               'Accept': 'application/vnd.aconex.issues.v2+json',
               'X-Application': '2909df20'}

    print(baseurl)
    response = getAPIResponse(baseurl, headers, "getting the Field issue")

    jsonResponse = json.loads(response)

    issueDesc = jsonResponse["description"]
    attachments = jsonResponse["attachments"]

    attachmentsUrls = [aXML['url'] for aXML in attachments]
    headers['Accept'] = "*/*"

    counter = 1
    for aurl in attachmentsUrls:
        url = baseurl + "/attachments/" + aurl.split("attachments/")[1]

        response = getAPIFile(url, headers, "getting the Field issue attachments")

        fpath =  PATH + folderpath + issueDesc + "\\"
        if not os.path.exists(fpath):
            os.makedirs(fpath)

        fpath += "\\" + str(counter) + ".jpg"
        print(fpath)

        with open(fpath, mode="wb") as file:
            file.write(response.content)

        counter += 1

    print("Downloaded photos for %s" % issueDesc)


def uploadFieldPhotos():
    global PROJECTURL
    PROJECTURL = config.env() + "/field-management/api/projects/" + config.project().projectID()

    global PATH
    PATH = str(pathlib.Path(__file__).parent.resolve()) + "\\PhotosToUpload\\"

    headers = {'Authorization': config.bearer(),
               'Accept': 'application/json'}

    PHOTOISSUEID = getPhotoIssueID()
    BASEAREAID = getAreasJson()["areas"][0]["id"] #get the top level area ID

    uploadFolders = []
    #Find folders of photos - create issue for each folder
    for root, dirs, files in os.walk(PATH):
        uploadFolders += dirs

    assert(len(uploadFolders) != 0)

    for folderName in uploadFolders:
        url = PROJECTURL + '/areas/' + BASEAREAID + '/issue'

        body = {
            "issue_type": {
                "id": PHOTOISSUEID
            },
            "description": folderName,
            "area": {
                "id": BASEAREAID
            },
        }

        response = postAPIResponse(url, headers, body, "creating the new Issue")
        jsonResponse = json.loads(response)
        issueID = jsonResponse["issue_id"]

        print("New issue %s created. Now uploading photos, please wait..." % folderName)
        addattachments(issueID, BASEAREAID, folderName)
        addIssueComment(issueID)
        markAsClosed(jsonResponse, BASEAREAID, folderName)
        print("Done. Please move to punchlist.")

def addattachments(issueID : str, areaID : str, folderName : str):
    #add attachments to newly created issue
    headers = {"Authorization": config.bearer(),
               "Accept": "*/*"}
    url = PROJECTURL + '/areas/' + areaID + "/issues/" + issueID + "/attachments"

    fpath = PATH + folderName

    for f in os.listdir(fpath):
        filepath = fpath + "\\" + f

        #Post request with new attachment file. You must post each file separately
        if os.path.isfile(filepath):
            ok = True
            fileext = os.path.splitext(f)[1]
            filesizebytes = os.path.getsize(filepath) #i cant find the actual size limit so im leaving it
            fileextshortname, _ = mimetypes.guess_type(f)
            if filesizebytes < 1:
                print("The file %s is so small it must be corrupted. Sus" % f)
                ok = False

            elif fileextshortname.startswith("image/"):
                filetype = "images"
            elif fileextshortname.startswith("video/"):
                filetype = "videos"
            elif fileextshortname in ["application/pdf", "application/msword"]:
                filetype = "documents"
            else:
                print("Unsupported file type for %s" % f)
                ok = False

            if ok:
                fileToUpload = [(filetype, (f, open(filepath, "rb"), fileextshortname))]
                postAPIFile(url, headers, fileToUpload, ("adding the Issue attachment with filename %s" % f))

    print("Attachments added successfully.")

def addIssueComment(issueID : str):
    #put participant ID as our org
    participantID = config.project().getMyOrgID()

    url = PROJECTURL + "/issues/" + issueID + "/participants/" + participantID + "/comments"
    body = {"content": "Auto created",
            "client_captured_at": datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%dT%H:%M:%S.%fZ")}
    headers = {'Authorization': config.bearer(),
               'Accept': 'application/json'}

    postAPIResponse(url, headers, body, "adding the Issue comment")

def markAsClosed(jsonIssue : str, areaID : str, issueDescription : str):
    issueID = jsonIssue["issue_id"]
    issueType = jsonIssue["issue_type"]

    headers = {"Authorization": config.bearer(),
               "Accept": "application/json"}
    url = PROJECTURL + '/areas/' + areaID + "/issues/" + issueID
    body = {"issue_id": issueID,
        "description": issueDescription,
            "issue_type": issueType,
        "status": "Closed"}

    putAPIResponse(url, headers, body, "marking the Issue as closed")