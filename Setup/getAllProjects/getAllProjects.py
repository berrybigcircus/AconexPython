import csv
import pathlib

import xml.etree.ElementTree as ET #for parsing xml


from Setup.config import config
from Setup.APIcommon import getAPIResponse


def main():
    ##Get list of my projects
    url = "https://api.aconex.com/api/projects/"
    headers = {'Authorization': config.bearer()}

    xml = getAPIResponse(url, headers=headers, explanation="getting the list of all projects")

    FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
    config.info("Writing to %s" % FOLDERPATH + "\\projectList.csv")
    csvfile = open(FOLDERPATH + "\\projectList.csv", "w", newline ='')
    writer = csv.writer(csvfile)
    writer.writerow(["pid", "pname", "pcode"])

    for project in ET.fromstring(xml.strip()).findall(".//Project[@Hidden='false']"): #find visible projects only
        pname = project.find('ProjectShortName').text
        pid = project.find('ProjectId').text
        pcode = project.find('ProjectCode').text #the only issue is on old projects where the code isn't loaded in properly, but should be ok
        writer.writerow([pid, pname, pcode])

    csvfile.close()
