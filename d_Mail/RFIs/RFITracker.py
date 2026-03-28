import datetime
import mimetypes
import os
import pathlib
from base64 import b64encode
from typing import Any

import pandas
import pickle

import xml.etree.ElementTree as ET  # for parsing xml

import requests
import win32com.client

from Setup.APIcommon import importLastRun, postAPIFile, postAPIResponse
from Setup.Directory import findMailingGroups, addUserIds
from Setup.FormField import createxmltemplate
from Setup.config import config
from Setup.Doc import searchForDoc, getDocumentLink

from Setup.Mail import AconexMail, getRFIMailTypes, getAllMail, getrfithread, searchForMail, \
    convertMailTypesToDict, AconexThread, getBallInCourt, openDraftLink, sendDraft, searchMail

mailData = {
    "Status": [],
    "Ball in Court": [],
    "Reference Number": [],
    "Subject": [],
    "Originally From": [],
    "RFI Description": [],
    "Discipline(s)": [],
    "Date RFI Sent": [],
    "RFI Response": [],
    "Date RFI Responded": [],
    "Latest Correspondence": [],
    "Comments": [],
    "Date Closed": [],
    "(Helper) Hyperlink": [],
    "Mail Number": []
}

def main():
    mailData.update((key, []) for key in mailData) #clear and reset dictionary
    global FOLDERPATH
    FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
    filename : str = FOLDERPATH + "\\Trackers\\" + config.project().projectCodePrefix()+"Exported Data.xlsx" #for this project, this is where the RFI data is read / written
    #importExcel(filename) #TODO - pull these

    lastrun : datetime.datetime = importLastRun(filename)

    #rfimailtypes = getRFIMailTypes(config.project(), config.mailtypes())
    #mtDict = convertMailTypesToDict(rfimailtypes)
    allRowsDicts : list[dict] = getrfithreadnew(loadpickle=True, lastrun=lastrun) #getrfithread(config.project(), getAllMail(config, rfimailtypes), mtDict)

    #convert into one dictionary
    for d in allRowsDicts:
        for k, v in d.items():
            mailData[k].append(v)

    print([len(l) for l in mailData.values()])
    exportToExcel(filename, mailData)

    rfipath = FOLDERPATH + "\\Trackers\\" + config.project().projectCodePrefix()+"RFI Tracker.xlsx"

    if os.path.exists(rfipath):
        uploadRFITracker(rfipath)
    else:
        config.logger.error("No RFI tracker file found. Please create tracker file to update the doc register")

def importExcel(filename) -> list[AconexMail]:
    try:
        excelDataDF = pandas.read_excel(open(filename, 'rb'), sheet_name="RawData")
        return createMailsFromDF(excelDataDF)
    except FileNotFoundError:
         return []

def createMailsFromDF(df) -> list[AconexMail]:
    aconexMails = []
    for index, serRow in df.iterrows():
        refno = serRow["Reference Number"]
        comments = serRow["Comments"]

        am = searchForMail(refno)
        am.setComment(comments)
        aconexMails.append(am)

    return aconexMails

def exportToExcel(filename, mailData):
    #create sheet to write the project information
    projectinfo = {
        "Project Name": [config.project().projectName()],
        "Date Generated": [datetime.datetime.today().strftime('%d/%m/%Y %H:%M')]
    }
    dataframe = pandas.DataFrame(data=projectinfo)
    if os.path.exists(filename):
        writer = pandas.ExcelWriter(filename, mode='a', engine='openpyxl', if_sheet_exists="replace")
    else:
        writer = pandas.ExcelWriter(filename, mode='w')

    dataframe.to_excel(writer,
           sheet_name="ProjectInfo",
           header= True,
           startrow = 0,
           index=False) #no index col

    dataframe = pandas.DataFrame(data=mailData)  # convert into pandas data frame for exporting
    dataframe.to_excel(writer,
                       sheet_name="RawData",
                       header=True,
                       startrow=0,
                       index=False)  # no index col

    writer.close()
    config.logger.info("     Mail data added to " + filename)


def getrfithreadnew(loadpickle = False, lastrun : datetime.datetime = None):
    rfimailtypes, rfireplymailtypes = getRFIMailTypes(config.project(), config.mailtypes())
    if not lastrun:
        loadpickle = False

    if loadpickle:
        try:
            fpath = FOLDERPATH + "mails.pkl"
            with open(fpath, "rb") as f:
                rfimails = pickle.load(f)
            f.close()
            config.logger.info("Loaded pickle")

            config.info("Getting RFI data since %s" % (datetime.datetime.strftime(lastrun, '%d/%m/%Y')))
            #check for new mails sent, and also check if mails have been closed out
            query = "(sentdate:[{lr} TO {now}] OR closedoutdate:[{lr} TO {now}])".format(lr=datetime.datetime.strftime(lastrun, "%Y%m%d"),
                                                      now=datetime.datetime.strftime(datetime.datetime.now(),
                                                                                     "%Y%m%d"))
            newmails: list[AconexMail] = list(
                filter(lambda m: not m.isVoid(), getAllMail(config, rfimailtypes, query)))

            rfimails += newmails
            #filter to one amail per reference number to avoid a duplicate row (by converting to dict then back again)
            rfimails = {mail.refno:mail for mail in rfimails}.values()

            with open(fpath, "wb") as f:
                pickle.dump(rfimails, f)
                config.logger.info("Mails dumped to pickle file")

            f.close()

        except:
            loadpickle = False


    if not loadpickle:
        rfimails: list[AconexMail] = list(filter(lambda m: not m.isVoid(), getAllMail(config, rfimailtypes)))
        fpath = FOLDERPATH + "mails.pkl"
        with open(fpath, "wb") as f:
            pickle.dump(rfimails, f)
            config.logger.info("Mails dumped to pickle file")

        f.close()

    allRows = []
    for rfimail in rfimails:
        thisRow = convertToRow(allRows, rfimail, rfimailtypes, rfireplymailtypes)
        allRows.append(thisRow)

    return allRows


def convertToRow(allRows: list[Any], rfimail: AconexMail, rfimailtypes, rfireplymailtypes) -> dict[Any, Any]:
    thisRow = {}

    thisRow["Subject"] = rfimail.subject
    thisRow["Originally From"] = rfimail.getFromOrg()
    thisRow["Date RFI Sent"] = rfimail.getDateTimeSent()
    thisRow["(Helper) Hyperlink"] = rfimail.getHyperlink()
    thisRow["Comments"] = rfimail.comments
    thisRow["RFI Description"] = rfimail.getFormFieldVal(config.project().getRFISetup()[0])
    thisRow["Discipline(s)"] = rfimail.getFormFieldVal(
        config.project().getRFIDiscSetup())  # it might not actually have one if it's a sc rfi, but try anyway
    thisRow["RFI Response"] = ""  # nothing for now
    thisRow["Date RFI Responded"] = ""
    thisRow["Ball in Court"] = "N/A"
    thisRow["Status"] = rfimail.getStatus()  # for now
    thisRow["Date Closed"] = rfimail.getClosedOutDate()

    rfithread = AconexThread(config, rfimail.threadid)

    lastresponse = rfithread.getLatestMail(rfithread.threadlist)

    thisRow["Reference Number"] = thisRow["Mail Number"] = rfithread.getRoot().mailno
    thisRow["Latest Correspondence"] = lastresponse.mailno
    # if RFI not replied to
    if rfimail.isLeaf():
        getBallInCourt(rfimail, allRows, thisRow)

    else:
        lastrfiresponse = rfithread.getLatestofTypes(rfireplymailtypes)
        rfiforward = rfithread.getLatestofTypes(rfimailtypes)

        if lastrfiresponse:
            thisRow["RFI Response"] = lastrfiresponse.getFormFieldVal(config.project().getRFIReplySetup()[0])
            thisRow["Date RFI Responded"] = lastrfiresponse.getDateTimeSent()
            thisRow["Status"] = "Responded" if rfimail.getStatus() != "Closed-Out" else "Closed-Out"

            if lastrfiresponse.isLeaf():
                # if it's not marked as closed out, the ball in court is the sender, who needs to reply or close out
                thisRow["Ball in Court"] = "N/A" if rfimail.isClosed() else rfimail.getFromOrg()
            else:
                othermail = lastrfiresponse.getLatestReply()
                if othermail.isOutstanding() and not rfimail.isClosed():
                    getBallInCourt(othermail, allRows, thisRow)
                    thisRow["Status"] = othermail.getStatus()
                    thisRow["Comments"] = othermail.body

                elif othermail.isResponded() and not rfimail.isClosed():
                    thisRow["Ball in Court"] = othermail.getFromOrg()
                    thisRow["Status"] = othermail.getStatus()

        if rfiforward and rfiforward != rfimail:
            thisRow["Discipline(s)"] = rfiforward.getFormFieldVal(config.project().getRFIDiscSetup())
            thisRow["RFI Description"] = rfiforward.getFormFieldVal(config.project().getRFISetup()[0])
            thisRow["Mail Number"] = rfiforward.mailno

            if rfiforward.isOutstanding() and not rfiforward.isClosed():
                thisRow["Status"] = rfiforward.getStatus()
                getBallInCourt(rfiforward, allRows, thisRow)

            if rfiforward != lastresponse and not lastrfiresponse:
                getBallInCourt(lastresponse, allRows, thisRow)
    return thisRow

#Refresh data connections
def refreshTracker(filepath):
    xlapp = win32com.client.DispatchEx("Excel.Application")
    wb = xlapp.Workbooks.Open( filepath)
    wb.RefreshAll()
    xlapp.CalculateUntilAsyncQueriesDone()
    wb.Save()
    xlapp.Quit()
    config.logger.info("RFI tracker refreshed")
    del wb
    del xlapp


def uploadRFITracker(filepath):
    refreshTracker(filepath)
    FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())

    filename = filepath.split("\\")[-1]

    docnumber = config.project().getRFIDocNumber()
    #check if tracker exists already
    config.logger.info("Searching for %s in doc register" % docnumber)
    returnfields = "title,revision,author,statusid,doctype,discipline,category,vdrcode,selectlist1"
    docxml = searchForDoc(config, "docno:{}".format(docnumber), returnfields)

    url = config.projecturl() + "/register/"
    headers = {'Authorization': config.bearer(),
               'Content-Type': 'multipart/mixed',
               'boundary': 'myboundary'}

    if docxml == None:
        config.logger.error("RFI Tracker not found in register. Please add a placeholder")
        exit()
    else:
        config.logger.info("RFI Tracker found in register.")

        doctemplatexml = createxmltemplate('Document', config.mandatorydocfields())
        root = doctemplatexml.getroot()
        for elem in root:
            existingval = docxml.find(elem.tag)
            if existingval is not None:
                elem.text = existingval.text

        docid = docxml.attrib.pop('DocumentId')
        url += docid + "/supersede"

        doctemplatexml.find('Revision').text = datetime.datetime.now().strftime("%Y/%m/%d")
        doctemplatexml.find('HasFile').text = "true"
        dn = doctemplatexml.find('DocumentNumber')
        root.remove(dn)

        # Type and Status is a required field but a list docs search only returns the name of the doc type, not the IDs
        doctypename = docxml.find('DocumentType').text
        doctypeid = config.docTypes()[doctypename]
        assert doctypeid is not None
        typeidxml = doctemplatexml.find('DocumentTypeId')
        typeidxml.text = doctypeid

        statusname = docxml.find('DocumentStatus').text
        docstatusid = config.docStatuses()[statusname]
        assert docstatusid is not None
        statusidxml = doctemplatexml.find('DocumentStatusId')
        statusidxml.text = docstatusid

        if config.searchForFormField('milestonedate'):
            mdate = ET.Element('milestonedate')
            mdate.text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            doctemplatexml.append(mdate)


        #ET.indent(root, space="", level=0)

        xmldata = "--myboundary\n\n" + ET.tostring(root, encoding='unicode') + "\n--myboundary\n\nX-Filename: " + filename + "\n\n"

        with open(filepath, "rb") as f: #read bytes of file
            encoded = b64encode(f.read())
            encStr = encoded.decode("utf-8")
            xmldata = xmldata + encStr + "\n\n--myboundary--"

        f.close()

        with open((FOLDERPATH + "\\text.txt"), "w") as f:
            f.write(xmldata)
        f.close()

        response = requests.post(url, headers=headers, data=xmldata)

        if response.status_code != 200:
            config.error("There was an error superseding RFI tracker. %s" % response.reason)
            exit()

        config.logger.info("RFI tracker superseded")
        xml = response.text
        newdocid = ET.fromstring(xml).find('RegisterDocument').text

        getDocumentLink(config.env(), newdocid)
        #registerTransmittal(newdocid)

#TODO
def registerTransmittal(docid: str):
    headers = {'Authorization': config.bearer(),
               'Content-Type': 'multipart/mixed',
               'boundary': 'myboundary'}

    url = config.projecturl() + "/mail?is_draft=true"

    mailtemplatexml = createxmltemplate('Mail', config.mandatorymailfields())
    root = mailtemplatexml.getroot()

    transmittalmt = list(filter(lambda mt: mt.typename()=="Transmittal", config.mailtypes()))[0]

    root.find('MailTypeId').text = transmittalmt.corrtypeid()
    root.find('MailSubject').text = "Latest RFI Tracker"
    root.find('TotalAttachmentCount').text = "1"
    root.find('RichMailText').text = "true"

    mbody = ET.Element("MailBody")
    mbody.text = "."
    root.append(mbody)

    adid = ET.Element("AttachedDocId")
    adid.text = docid
    root.append(adid)

    #register it as coming from NM
    fromid = ET.Element('FromUserId')
    fromid.text = config.project().getMyUserID()
    root.append(fromid)

    #Set 'reason for issue' to issued for info
    reasonforissue = ET.Element('ReasonForIssue')
    reasonforissue.text = "4"
    root.append(reasonforissue)

    #Get the list of user IDS to send this transmittal to, based on people in the configured mailing groups
    mgroups : list [str] = config.project().getDistributeMGs()
    _, userIds = findMailingGroups(config, mgroups)
    touserid = root.find('ToUserId')
    root.remove(touserid)
    addUserIds(root,'ToUserId', userIds)

    ET.indent(root, space="", level=0)
    print(ET.tostring(root, encoding='unicode'))

    xmldata = ("--myboundary\nContent-Type: application/vnd.aconex.mail.v3+xml\n\n" +
               ET.tostring(root, encoding='unicode') + "\n--myboundary\n\nX-DocumentId: " + docid + "\n\n--myboundary--")

    response = requests.post(url, headers=headers, data=xmldata)

    FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
    with open((FOLDERPATH + "\\text.txt"), "w") as f:
        f.write(xmldata)
    f.close()

    if response.status_code != 200:
        config.error("There was an error transmitting the RFI tracker. %s" % response.reason)
        print(response.text)
        exit()

    config.logger.info("RFI tracker drafted")
    draftedMailId = ET.fromstring(response.text.strip()).find('NewMailId').text
    draftMailURL = config.env() + "/rsrc/20250422.1347/en_AU_DOC/mail/view/index.html#/" + config.project().projectID() + "/" + draftedMailId

    openDraftLink(config, response.text)
    #sendDraft(draftMailURL) TODO


def test():
    luceneQuery = "matchAll:1 NOT HBVoid AND docno:HBC-RFI-000050"
    mailtypes = config.mailtypes()
    rfimails = searchMail(config, luceneQuery, mailtypes)

    rfimailtypes, rfireplymailtypes = getRFIMailTypes(config.project(), config.mailtypes())

    allRows = []

    for rfimail in rfimails:
        thisRow = convertToRow(allRows, rfimail, rfimailtypes, rfireplymailtypes)

        for key, val in thisRow.items():
            print("{}: {}".format(key, val))