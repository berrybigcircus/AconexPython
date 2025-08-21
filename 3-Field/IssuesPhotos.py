import OAuth.config as config
from OAuth.APIcommon import putAPIResponse, postAPIResponse
import base64

def main():

    #/api/projects/{project_id}/areas/{area_id}/issues/{issue_id}/attachments
    PROJECTURL = config.env() + "/field-management/api/projects/" + config.project().projectID()  # field api urls are built around the env url

    #create issue
    areaid = '271341877549073131'
    url = PROJECTURL + '/areas/' + areaid + '/issue'
    headers = {'Authorization': config.bearer(),
               'Accept': 'application/json'}

    body = {
        "issue_type": {
                "id": "271341877549074071" #Photos issue type
            },
        "description": "Test",
        "area": {
            "id": areaid
        }
        }

    #createdIssue = postAPIResponse(url, headers, body, "creating the Issue")
    issueID = "ee289118-6d45-4f06-b5bf-ca647e8a7d8e" #createdIssue["issue_id"]

    #add attachments
    url = PROJECTURL + '/areas/' + areaid + "/issues/" + issueID + "/attachments"

    path = r"C:\Users\nicole.millinship\PycharmProjects\AconexPython\Test photos\20241210_102630.jpg"
    with open(path, "rb") as f:
        encoded_image = base64.b64encode(f.read())
        encStr = encoded_image.decode('utf-8')

    xmlFile = open(r"C:\Users\nicole.millinship\PycharmProjects\AconexPython\3-Field\issueAttachments.xml", "r")
    xmlData = xmlFile.read()
    xmlFile.close()
    xmlData = xmlData + encStr + "\n--***mime===boundary***--"
    xmlData.replace("FILENAME_HERE", "20241210_102630.jpg")
    body = {xmlData}

    postAPIResponse(url, headers, body, "adding the Issue attachment")