import os
import pandas
import Setup.config as config
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
from Setup.APIcommon import getAPIResponse, postAPIResponse, putAPIResponse


def main():
    REPLACEDBYID = "70b2a21c-145a-4834-a2b8-2c6af9bd44e2" #this is the direction ID for replaced by
    filename = "RelatedItemsTemplate.xlsx"
    df = importExcel(filename)

    docNumbersToFind : list = df["Document Number"].values.tolist()
    relatedItemDocNumbers : list = df["Replaced by"].values.tolist()

    #Search for the documents
    docsXml, notFound = searchForDocuments(docNumbersToFind)

    #Search for the related items documents
    relDocsXml, rNotFound = searchForDocuments(relatedItemDocNumbers)

    #assert len(docNumbersToFind) == len(docsXml)
    #assert len(relatedItemDocNumbers) == len(relDocsXml)

    headers = {'Authorization': config.token(), #use basic auth rather than bearer
               'Accept': 'application/vnd.aconex.document.relationship.v1+xml'}


    #Add related items to the found documents
    for docXML, relDocXML in zip(docsXml, relDocsXml):

        docid = docXML.attrib["DocumentId"]
        relDocID = relDocXML.attrib["DocumentId"]

        #config.env() + "/projects/" + config.project().projectID()
        url = config.projecturl() + "/documents/" + docid + "/relationships/" + REPLACEDBYID + "/related-documents/" + relDocID

        body = """<Relationship>
          <Document Id="271341877549511145">
            <Links>
              <Link Rel="self" Href="https://ea1.aconex.com/api/projects/1879048648/registeradata
            </Links>
          </Document>
          <Direction Id="70b2a21c-145a-4834-a2b8-2c6af9bd44e2"/>
          <RelatedDocument Id="271341877549511149">
            <Links>
              <Link Rel="self" Href="https://ea1.aconex.com/api/projects/187904864811149/metadata
            </Links>
          </RelatedDocument>
        </Relationship>"""

        print(url)
        print(postAPIResponse(url=url, headers=headers, body=body, explanation="getting the related item relationship"))

        exit()


def searchForDocuments(docNumbers):
    searchquery = " OR ".join([("docno:\"" + dn + "\"") for dn in docNumbers])
    docsXml = searchDocRegister(searchquery)

    foundocnos = list(map(lambda x: x.find("DocumentNumber").text, docsXml))
    notFound : list[str] = list(set(docNumbers) - set(foundocnos))

    return docsXml, notFound

def importExcel(fname : str):
    if not os.path.exists(fname):
        print("File not found")
        return

    xl = pandas.ExcelFile(fname)
    df = xl.parse("Sheet1")

    return df


def searchDocRegister(searchquery):
    parameters = {"search_type": "PAGED", #PAGED, meaning return results by "pages" of variable size.
                  "return_fields": "docno,title,doctype,revision,trackingid",
                  "search_query": searchquery,
                  "page_size": "500"
                  } 

    headers = {'Authorization': config.bearer()}
    url = config.projecturl() + "/register?" + urlencode(parameters)

    xml = getAPIResponse(url, headers, "searching document register")
    print(xml)
    searchXml = ET.fromstring(xml.strip()).findall('SearchResults/')
    totalPages: int = int(ET.fromstring(xml.strip()).get('TotalPages'))

    currentPageNum = 1
    while currentPageNum < totalPages:
        currentPageNum += 1
        url = config.projecturl() + "/register?" + urlencode(parameters) + "&page_number=" + str(currentPageNum)
        xml = getAPIResponse(url, headers, "searching document register")

        searchXml.extend(ET.fromstring(xml.strip()).findall('SearchResults/'))

    return searchXml