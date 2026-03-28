import requests #for making http requests
import json #for reading json
from urllib.parse import urlencode #encode urls
import xml.etree.ElementTree as ET #for parsing xml

import c_Field.Fieldclasses as classes
from Setup.APIcommon import getAPIResponse, putAPIResponse, jprint

def main(passedBearer, env):
    global bearer
    bearer = passedBearer
    global aconexEnv
    aconexEnv = env

    #use HB Test 1 as an example project
    global chosenProjectID
    chosenProjectID = "1879048648"
    global PROJECTURL
    PROJECTURL = aconexEnv + "/field-management/api/projects/" + chosenProjectID  #field api urls are built around the env url

    headers = {'Authorization': bearer,
               'Accept': 'application/json'} #all the responses are in json format


    areaID = "271341877549073051" #test on this area
    url = PROJECTURL + "/areas/" + areaID + "/checklists" #get all inspections in this area

    response = getAPIResponse(url, headers, "getting the Field inspections")
    jsonResponse = json.loads(response)

    for checklistJson in jsonResponse["checklists"]:
        templateTitle : str = checklistJson["template_title"]
        if templateTitle == "Hotworks Permit":
            pdfformname = "IMS-HBS-OHS26-T07 - Hot Works Permit - Edited.pdf"
            creator = classes.HotworksMap(rawJson=checklistJson,filename=pdfformname)

        elif templateTitle == "Permit to Dig":
            pdfformname = "IMS-HBS-OHS26-T02 - Permit to Dig - Edited.pdf"
            creator = classes.DigMap(rawJson=checklistJson, filename=pdfformname)
        else:
            print("An export for a %s type Field template hasn't been created yet." %templateTitle)
            continue

        # TODO - link to the field inspection
        creator.hyperlinkFunction(getRegisterLink)
        creator.export(templateTitle, "HB Test")

def getRegisterLink(valToSearchFor: str) -> str | None:
    parameters = {"search_type": "PAGED",
                  "return_fields": "trackingid",
                  "search_query": "docno:" + valToSearchFor
                  }
    url = "https://api.aconex.com/api/projects/" + chosenProjectID + "/register?" + urlencode(parameters) #search register
    headers = {'Authorization': bearer}

    xml = getAPIResponse(url, headers, "Searching the document register")
    if not xml:
        return None
    doc = ET.fromstring(xml.strip()).find('SearchResults/Document')
    trackingid = doc.find("TrackingId").text

    #you can't get this value as a return field, so we have to recreate it
    hyperlink = aconexEnv + "/ViewDoc?trackingid={}&projectid={}&cversion=1&tab=0".format(trackingid,chosenProjectID)
    return hyperlink



def xmlprint(xml):
    for child in xml.iter():
        if child.text:
            if child.text.strip():
                print(child.tag + " = " + child.text)