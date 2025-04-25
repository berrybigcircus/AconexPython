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

    for project in ET.fromstring(xml.strip()).findall(".//Project[@Hidden='false']"): #find visible projects only
        pname = project.find('ProjectShortName').text
        pid = project.find('ProjectId').text
        pcode = project.find('ProjectCode').text #the only issue is on old projects where the code isn't loaded in properly, but should be ok

        projectList[pid] = [pname, pcode]

    fp = open("projectList.txt","wb")
    print(projectList)
    pickle.dump(projectList, fp)
    fp.close()
