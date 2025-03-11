from symtable import Function

import requests #for making http requests
import json #for reading json
from base64 import b64encode
from urllib.parse import urlencode
import xml.etree.ElementTree as ET #for parsing xml
import pickle
import pandas #for exporting to excel
import openpyxl

global rowIndex
rowIndex = 1

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

def searchForDoc(docNumber):
    searchTerm = "docno:" + docNumber
    parameters = {"search_type": "PAGED",  # PAGED, meaning return results by "pages" of variable size.
                  "return_fields": "trackingid,docno,title,revision,reviewstatus,reviewSource", #use the tracking id because the doc no might change
                  "search_query": searchTerm
                  }

    headers = {'Authorization': bearer}
    url = PROJECTURL + "/register?" + urlencode(parameters)

    response = requests.get(url, headers=headers) #TODO - validate http
    xml = response.text

    docXml = ET.fromstring(xml.strip()).find('SearchResults/') #there is only one doc returned so can use find rather than findall

    #if 0 search results
    if docXml == None:
        print("Error - Document could not be found in the register with the number %s" % docNumber)
        return

    docReviewStatus = docXml.find('ReviewStatus').text

    docTitle = docXml.find('Title').text
    docRevision = docXml.find('Revision').text
    print("Document %s - %s (Current Rev = %s)" % (docNumber, docTitle, docRevision))
    #check if doc is in a workflow already
    if docReviewStatus == "Pending":
        docReviewSource = docXml.find('ReviewSource').text
        print("     Document %s is already in a workflow - %s" % (docNumber, docReviewSource))
        #TODO - can we open the link to this workflow

    else:
        docTrackingID = docXml.find('TrackingId').text
        searchForWorkflow(docNumber, docTitle, docTrackingID)

def searchForWorkflow(docNumber, docTitle, trackingId):
    #get all workflows on the project - unfortunately you can't just search for one document's workflows or anything like that

    global rowIndex
    headers = {'Authorization': bearer}
    url = PROJECTURL + "/workflows?"

    response = requests.get(url, headers=headers) #TODO - validate http
    xml = response.text

    #find the document's workflow reviews, using the tracking id
    wfReviewsXml = ET.fromstring(xml.strip()).findall("SearchResults/Workflow/[DocumentTrackingId='{}']".format(trackingId))
    wfReviewsXml.sort(key=lambda step: step.find('DateCompleted').text) #ensure comments are sorted by date (earliest to latest)

    workflowData = {
        "DocumentNumber": [], #this will be the same val each time
        "DocumentTitle":[],
        "WorkflowNumber": [],
        "DocumentRevision": [],
        "Reviewer": [],
        "StepOutcome": [],
        "DateCompleted": [],
        "Comments": []
    }

    for reviewXml in wfReviewsXml: #in case it's been in multiple reviews
        workflowData["WorkflowNumber"].append(reviewXml.find('WorkflowNumber').text)
        workflowData["DocumentRevision"].append(reviewXml.find('DocumentRevision').text)
        workflowData["Reviewer"].append(
            " - ".join([reviewXml.find('Reviewer/Name').text,
                       reviewXml.find('Reviewer/OrganizationName').text]))
        workflowData["StepOutcome"].append(reviewXml.find('StepOutcome').text)
        workflowData["DateCompleted"].append(reviewXml.find('DateCompleted').text)
        workflowData["Comments"].append(reviewXml.find('Comments').text)

        workflowData["DocumentNumber"].append(docNumber)
        workflowData["DocumentTitle"].append(docTitle)

    # export the comment data into excel
    dataframe = pandas.DataFrame(data=workflowData)  # convert into pandas data frame for exporting
    with pandas.ExcelWriter('PreviousComments.xlsx',mode='a', if_sheet_exists='overlay') as writer:
        dataframe.to_excel(writer,
                           sheet_name="Sheet1",
                           header=False, #no header col (already set up within the spreadsheet)
                           startrow = rowIndex,
                           index=False) #no index col
        rowIndex += len(dataframe.index) #add num of rows to index, to start at next empty row
    print("     Workflow data added to excel.")

def main(passedBearer, env):
    global bearer
    bearer = passedBearer
    global aconexEnv
    aconexEnv = env
    ##Ask for project
    try:
        fp = open("../getAllProjects/projectList.txt", "rb")  # load stored projects
        projectsList = pickle.load(fp)  # load as project dictionary
        fp.close()
    except:
        print("Error loading project list.")
        exit()

    print("CURRENT PROJECTS:")
    for i, (pName, pID) in enumerate(projectsList.items()):  # print projects to user
        print("    %d - %s (%s)" % (i, pName, pID))

    debug = False  #### <---
    confirm = "n"
    global chosenProjectID

    if debug == True:
        chosenProjectID = "1879048648"
        confirm = "Y"

    while confirm.upper() != "Y" and confirm.lower() != "yes":
        projectIndex = indexInput(len(projectsList) - 1)
        print("Project - %s" % list(projectsList)[projectIndex])

        confirm = input("Confirm (Y/N):")
        chosenProjectID = list(projectsList.values())[projectIndex]

    global PROJECTURL
    PROJECTURL = "https://api.aconex.com/api/projects/" + chosenProjectID  # url of the chosen project (using project id)

    #get the documents to search for using the input text file
    file = open("docsList.txt", "r")
    textLines = [line.rstrip() for line in file]
    textLines = textLines[1::]  # remove top info line
    file.close

    for iLine in textLines:
        #search up the user's doc number
        searchForDoc(iLine)