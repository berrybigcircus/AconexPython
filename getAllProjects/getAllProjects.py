import requests #for making http requests
import json #for reading json
from base64 import b64encode
from urllib.parse import urlencode
import xml.etree.ElementTree as ET #for parsing xml
import re #regex
import pickle


def main(bearer):
    ##Get list of my projects
    url = "https://api.aconex.com/api/projects/"
    headers = {'Authorization': bearer}

    response = requests.get(url, headers=headers)

    print(str(response.status_code) + " " + response.reason)

    xml = response.text

    ##for testing:
    ##f = open("xmlTest.txt","r")
    ##xml = f.read()
    ##f.close()

    projectList = dict()

    for project in ET.fromstring(xml.strip()).findall(".//Project[@Hidden='false']"): #find visible projects only (assume hidden aren't getting new users added to)
        name = project.find('ProjectShortName').text
        pid = project.find('ProjectId').text

        projectList[name] = pid

    fp = open("projectList.txt","wb")
    print(projectList)
    pickle.dump(projectList, fp)
    fp.close()
