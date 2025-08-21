import datetime
from datetime import datetime
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import markdownify

from OAuth.APIcommon import getAPIResponse, convertToDateTime
import OAuth.config as config

class AconexFormField:
    def __init__(self, label, fid, value=None):
        self.__label : str = label
        self.__identifier : str = fid
        self.__value : str = value

    def label(self) -> str:
        return self.__label

    def value(self) -> str:
        return self.__value

    def setValue(self, val : str):
        self.__value = val

    def debug(self):
        print(self.__identifier)


class AconexMailType:
    def __init__(self, typeID, typeName):
        self.__typeID : str = typeID
        self.__typeName : str = typeName
        self.__projectFields : list[AconexFormField] = None

    def corrtypeid(self) -> str:
        return self.__typeID

    def typename(self) -> str:
        return self.__typeName

    def debug(self) :
        print(self.__typeName)

    #Use API to get schema for the mail type's form field
    def getFormFields(self, fflink : str):
        self.__projectFields = []
        headers = {'Authorization': config.bearer(),
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}

        url = config.env() + fflink
        xml = getAPIResponse(url=url, headers=headers, explanation="getting the form fields for the specified mail.")

        formFieldsXml = ET.fromstring(xml.strip()).findall('MailFormField')
        for ffXML in formFieldsXml:
            label = ffXML.find('Label')
            fid = ffXML.get('identifier')
            self.__projectFields.append(AconexFormField(label.text, fid))

class AconexUser():
    def __init__(self, name, org, disttype):
        self.__name : str = name
        self.__org : str = org
        self.__disttype : str = disttype

    def name(self) -> str:
        return self.__name

    def org(self) -> str:
        return self.__org

    def wasSentFrom(self) -> bool:
        return self.__disttype == "FROM"

    def wasSentTo(self) -> bool:
        return self.__disttype == "TO" #if it was to them, not cc, bcc, or sent by them


class AconexMail():
    def __init__(self, mailid="", mailXML : ET.Element=None, comments=""):
        self.mailno : str = None

        if mailXML == None: #if list mail hasn't been run
            self.mailid = mailid
            self.viewMailMetadata() #now we will have a mailno
            if self.mailno.startswith("DRAFT"): #sometimes - when getting a mail thread, it will have picked up a draft. if so, exit asap
                self.privateNote = "HBVoid"
                return
            luceneQuery = valQuery(self.mailno)
            mailXML = getMailList(luceneQuery)[0]

        else:
            self.mailno = mailXML.find("MailNo").text
            self.mailid = mailXML.get("MailId")

        self.refno =  mailXML.find("ReferenceNumber").text
        self.subject = mailXML.find("Subject").text
        self.hasAttach(mailXML.find("HasAttachments").text)

        self.sentDate(mailXML.find("SentDate").text)
        self.responsereqDate = self.checkForDate(mailXML.find("ResponseRequired/ResponseRequiredDate"))
        self.closedoutDate = self.checkForDate(mailXML.find("ClosedOutDetails/ClosedOutDate"))

        self.mailtypename = mailXML.find("CorrespondenceType").text
        self.mailtype: AconexMailType

        recipientsXML = mailXML.findall("ToUsers/Recipient")
        toUsers = []
        for recXML in recipientsXML:
            name = recXML.find("Name").text
            organisation = recXML.find("OrganizationName").text
            disttype = recXML.find("DistributionType").text
            toUsers.append(AconexUser(name, organisation, disttype))
        self.toUsers = toUsers

        fromuserXML = mailXML.find("FromUserDetails")
        fromname = fromuserXML.find("Name").text
        fromorg = fromuserXML.find("OrganizationName").text
        self.From = AconexUser(fromname, fromorg, "FROM")

        self.hyperlink: str = self.getHyperlink()  # as per usual i have to write it myself SMH

        self.isRoot: bool = self.mailno == self.refno # if the ref number is this mail - then it is the start of thread
        self.RootMail: AconexMail
        self.getRootMail()

        self.Replies : list[(AconexMail, str)] = []

        self.formfields : list[AconexFormField] = []

        self.comments = comments  # the only man-made field

        self.status: str
        self.threadid: str
        self.body: str
        self.privateNote: str = ""

    def checkForDate(self, dateXML : ET.Element) -> datetime:
        if dateXML is not None:
            return datetime.strptime(dateXML.text, "%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            return None
    def responsereqDate(self, responsereqdate : ET.Element):
        if responsereqdate is not None:
            self.__responsereqdate = datetime.strptime(responsereqdate.text, "%Y-%m-%dT%H:%M:%S.%fZ")


    def sentDate(self, sentdate : str):
         self.__sentdate = datetime.strptime(sentdate, "%Y-%m-%dT%H:%M:%S.%fZ")

    def hasAttach(self, hasAttach : str):
        self.__hasAttachments = hasAttach == "true"

    def isRoot(self) -> bool:
        return self.mailno == self.refno

    def debug(self):
        print(self.mailno + ": " + self.subject)

    def setComment(self, comment: str):
        self.comments = comment

    def setMailType(self, filterTypes: dict):
        self.mailType = filterTypes[self.mailtypename]

    def viewMailMetadata(self):
        headers = {'Authorization': config.bearer(),
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}
        url = config.projecturl() + "/mail/" + self.mailid

        xml = getAPIResponse(url, headers, "getting mail metadata for mail id: " + self.mailid)
        root = ET.fromstring(xml.strip())

        #if it has not been fed values for these already
        if not self.mailno:
            self.mailno = root.find("MailNo").text

        # there can be multiple notes, but since you can't delete - take the last one as the important one (i'm assuming the notes are in date order)
        notes = root.findall("Notes/Note/NoteContents")
        if notes: self.privateNote = notes[-1].text

        self.body = markdownify.markdownify(root.find("MailData").text) if root.find("MailData").text is not None else ""
        self.status = root.find("Status").text
        self.threadid = root.find("ThreadId").text
        self.getMailThread()

        self.getFormFields(root.findall("MailFormFields/MailFormField"))

    def isVoid(self) -> bool:
        return self.privateNote == "HBVoid"

    def isClosed(self) -> bool:
        return self.status == "Closed-Out" or self.status == "N/A"

    #if status is outstanding or overdue
    def isOutstanding(self) -> bool:
        return self.status == "Overdue" or self.status == "Outstanding"

    def isResponded(self) -> bool:
        return self.status == "Responded" or self.status == "Partial"

    def getFormFields(self, formfieldsXML):
        self.formfields = []

        for ffXML in formfieldsXML:
            label = ffXML.find("Label").text
            ident = ffXML.find("Identifier").text
            value = ffXML.find("Value").text
            self.formfields.append(AconexFormField(label, ident, value))

    # using the label name of the form field, return its value
    def getFormFieldVal(self, label : str) -> str:
        ffvals = [ff.value() for ff in self.formfields if ff.label() == label]
        if len(ffvals) == 1:
            return ffvals[0]
        return None

    def getHyperlink(self) -> str:
        return (config.env() + "/hub/index.html?mainTarget=%2FViewCorrespondence%3FPROJECT_ID%3D" + config.project().projectID() +
                "%26CORRESPONDENCE_MAILBOX%3D0%26Correspondence_ID%3D" + self.mailid)

    def getRootMail(self):
        if self.isRoot:
            self.RootMail = None #this is the root
        else:
            self.RootMail = searchForMail(self.refno)

        return self.RootMail

    def getMailThread(self):
        self.Replies = []
        #call getMaiLThread
        headers = {'Authorization': config.bearer(),
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}
        url = config.projecturl() + "/mail/" + self.threadid + "/thread"
        xml = getAPIResponse(url, headers, "getting the mail thread for " + self.mailno)

        # filter to where we currently are in the thread, to prevent an endless loop - we just want this mail's replies/forwards
        threadXML = ET.fromstring(xml.strip()).findall("Mail")

        replyMailsXML = readThread(threadXML, self.mailid)
        replyMailsXML = replyMailsXML.findall("Replies/Mail")

        for rpMXML in replyMailsXML:
            mailid = rpMXML.get("MailId")
            repMail = AconexMail(mailid=mailid, mailXML=None)
            repType : str = rpMXML.find("ReplyType").text
            if not repMail.isVoid():
                self.Replies.append((repMail,repType))

    def getFromOrg(self) -> str:
        return self.From.org()

    def getToOrgs(self) -> [str]:
        return list(set([to.org() for to in self.toUsers if to.wasSentTo()]))

    #get each org the action is with - group client orgs together
    def getBallInCourt(self) -> [str]:
        #check if this project has a certain name/org mapping
        orgMap = config.project().getOrgMap()
        if orgMap is None:
                return self.getToOrgs()
        else:
            bic = []
            for to in self.toUsers:
                name, org = to.name(), to.org()
                if (name, org) in orgMap:
                    map = orgMap[(name, org)]
                    if map != "Ignore": bic.append(map)
                else:
                    bic.append(org)

            return list(set(bic))


    def getDateTimeSent(self) -> str:
        return datetime.strftime(self.__sentdate, "%d/%m/%Y %H:%M")

    def getClosedOutDate(self) -> str:
        if self.closedoutDate:
            return datetime.strftime(self.closedoutDate, "%d/%m/%Y %H:%M")
        else:
            return ""

def getThisMail(threadXML : [ET.Element], mailid : str) -> ET.Element:
    thisMailXML = list(filter(lambda m: m.get("MailId") == mailid, threadXML))
    if len(thisMailXML) != 0:
        return thisMailXML[0]

    for mailXML in threadXML:
        newthreadXML = mailXML.findall("Replies/Mail")
        if len(newthreadXML) > 0:
            foundMail = readThread(newthreadXML, mailid)
            if foundMail is not None:
                return foundMail

def readThread(threadXML : [ET.Element], mailid : str) -> ET.Element:
    thisMailXML = list(filter(lambda m: m.get("MailId") == mailid, threadXML))
    if len(thisMailXML) == 0 and len(threadXML) > 0:
        for mailXML in threadXML:
            newthreadXML = mailXML.findall("Replies/Mail")
            if len(newthreadXML) > 0:
                foundMail = readThread(newthreadXML, mailid)
                if foundMail is not None:
                    return foundMail
    else:
        return thisMailXML[0]

def getMailTypes(mailSchemaXML) -> list[AconexMailType]:
    mailTypesXML = mailSchemaXML.find(
        "./MultiValueSchemaField/./[Identifier='MailTypeId']")  # find the field for mail types

    mailTypesXML = mailTypesXML.findall("SchemaValues/SchemaValue")
    mailTypes: list[AconexMailType] = []

    for elem in mailTypesXML:
        typeName = elem.find('Value').text

        m = AconexMailType(typeID=elem.find('Id').text, typeName=typeName)
        ffLink = elem.find(
            'Links/Link')  # link to api request that will give you the details for the form fields for that mail type
        if ffLink is not None:
            m.getFormFields(ffLink.get('href'))
        mailTypes.append(m)

    return mailTypes

def getProjectInviteMailID(mailtypes : list[AconexMailType]) -> str:
    #Advice mail type is for HB Test
    projectInviteMail = list(filter(lambda mt : mt.typename() in ["Project Invitation","Advice"], mailtypes))
    return projectInviteMail[0].corrtypeid()

def getRFIMailTypes(mailTypes : list[AconexMailType]) -> list[AconexMailType]:
    return list(filter(lambda mt: mt.typename() in config.project().getRFISetup()[1], mailTypes))


def convertMailTypesToDict(mailTypes : list[AconexMailType]) -> dict[str, AconexMailType]:
    filterDict = {mt.typename(): mt for mt in mailTypes}
    return filterDict

#get all RFI mails
def getAllMail(mailTypes : list[AconexMailType]) -> list[dict]:
    corrTypesIDs = [mType.corrtypeid() for mType in mailTypes]
    luceneQuery = "corrtypeid:" + " OR corrtypeid:".join(corrTypesIDs)

    mailsReturnedXML = getMailList(luceneQuery)

    #sort by ref number, then by earliest of that ref number. i want only one mail per ref number - and i want the 'parent'
    #this would break if a rfi was forwarded twice from one non-rfi parent - like from a transmittal, two rfis were forwarded off it. i am hoping this doesn't happen so it's okay
    # * -1 = sort descending
    mailsReturnedXML = sorted(mailsReturnedXML, key=lambda mail: (mail.find("ReferenceNumber").text, convertToDateTime(mail.find("SentDate").text)))
    mtDict = convertMailTypesToDict(mailTypes)

    filterMails = createAMails(mailsReturnedXML, mtDict)

    #We now have all the RFI mails, we need to figure out the threads
    allRows = []

    for rfiMail in filterMails:
        thisRow = {}
        thisRow["Latest Correspondence"] = rfiMail.mailno
        if rfiMail.isRoot:
            thisRow["Reference Number"] = rfiMail.mailno
        #if the 'rfi' mail was not the start of the thread
        else:
            thisRow["Reference Number"] = rfiMail.RootMail.mailno

        rfiMail.setMailType(mtDict) #set the AconexMaiLType object
        thisRow["Subject"] = rfiMail.subject
        thisRow["Originally From"] = rfiMail.getFromOrg()
        thisRow["Date RFI Sent"] = rfiMail.getDateTimeSent()
        thisRow["(Helper) Hyperlink"] = rfiMail.getHyperlink()
        thisRow["Comments"] = rfiMail.comments
        thisRow["RFI Description"] = rfiMail.getFormFieldVal(config.project().getRFISetup()[0])
        thisRow["Discipline(s)"] = rfiMail.getFormFieldVal(config.project().getRFIDiscSetup()) #it might not actually have one if it's a sc rfi, but try anyway
        thisRow["RFI Response"] = "" #nothing for now
        thisRow["Date RFI Responded"] = ""
        thisRow["Ball in Court"] = ""
        thisRow["Status"] = "" #for now
        thisRow["Date Closed"] = rfiMail.getClosedOutDate()

        #if RFI not replied to
        if not rfiMail.Replies:
            thisRow["Status"] = rfiMail.status
            getBallInCourt(rfiMail, allRows, thisRow)
            allRows.append(thisRow)
        else:
            replies = rfiMail.Replies
            getReplies(rfiMail, replies, allRows, thisRow) #allRows will be auto updated because the dict is a pointer

    return allRows

#the ball in court is everyone who it was sent to who hasn't replied, so add a new row for each org
def getBallInCourt(mail : AconexMail, allRows, thisRow):
    toOrgs = mail.getBallInCourt()
    thisRow["Ball in Court"] = toOrgs[0]

    #if more than one org, create new rows for each. otherwise just return thisRow with the BoC
    for org in toOrgs[1:]:
        firstRow = thisRow.copy()
        firstRow["Ball in Court"] = org
        allRows.append(firstRow)

def getReplies(ogMail, replies, allRows, thisRow):
    for replyMail, mRType in replies:
        thisRow["Latest Correspondence"] = replyMail.mailno
        replyMail.viewMailMetadata()  # ensure mail metadata and replies are loaded
        if mRType == "REPLY":
            # if rfi reply mail type
            if replyMail.mailtypename in config.project().getRFIReplySetup()[1]:
                thisRow["Discipline(s)"] = replyMail.getFormFieldVal(config.project().getRFIDiscSetup())
                thisRow["RFI Response"] = replyMail.getFormFieldVal(config.project().getRFIReplySetup()[0])
                thisRow["Date RFI Responded"] = replyMail.getDateTimeSent()
                thisRow["Status"] = ogMail.status

                #if it's not marked as closed out, the ball in court is the sender, who needs to reply or close out
                thisRow["Ball in Court"] = "N/A" if ogMail.isClosed() else ogMail.getFromOrg()

            #if a gc / other mail type
            else:
                if replyMail.isOutstanding(): #if this gc is awaiting a response
                    thisRow["Status"] = replyMail.status
                    getBallInCourt(replyMail, allRows, thisRow)
                    thisRow["Comments"] = replyMail.body #this might not be the best way of doing it

        elif mRType == "FORWARD":
            # if fwded as rfi
            if replyMail.mailtypename in config.project().getRFISetup()[1]:
                thisRow["RFI Description"] = replyMail.getFormFieldVal(config.project().getRFISetup()[0])
                thisRow["Date RFI Sent"] = replyMail.getDateTimeSent()
                thisRow["Discipline(s)"] = replyMail.getFormFieldVal(config.project().getRFIDiscSetup())
                thisRow["RFI Response"] = ""  # nothing for now
                thisRow["Date RFI Responded"] = ""

                # if fwded RFI not replied to
                if not replyMail.Replies:
                    thisRow["Status"] = replyMail.status
                    getBallInCourt(replyMail, allRows, thisRow)

            #if fwded as response to rfi
            if replyMail.mailtypename in config.project().getRFIReplySetup()[1]:
                thisRow["RFI Response"] = replyMail.getFormFieldVal(config.project().getRFIReplySetup()[0])
                thisRow["Date RFI Responded"] = replyMail.getDateTimeSent()
                thisRow["Status"] = "Responded"
                thisRow["Ball in Court"] = ogMail.getFromOrg()

            #if fwded as gc / other mail
            else:
                if replyMail.isOutstanding(): #if this gc is awaiting a response
                    thisRow["Status"] = replyMail.status
                    getBallInCourt(replyMail, allRows, thisRow)
                    thisRow["Comments"] = replyMail.body #this might not be the best way of doing it

        rmReplies = replyMail.Replies

        if len(rmReplies) > 0:
            newRow = thisRow.copy()
            getReplies(replyMail, rmReplies, allRows, newRow)

        else:
            allRows.append(thisRow)

#wrapper to search the inbox and the sent box
def getMailList(luceneQuery)  -> [str]:
    iXML = getMailsForMailbox("inbox", luceneQuery)  # in inbox
    sXML = getMailsForMailbox("sentbox", luceneQuery) # in sent box
    return ET.fromstring(iXML.strip()).findall("SearchResults/Mail") + ET.fromstring(sXML.strip()).findall("SearchResults/Mail")

#Convert mail xml to Aconex Mail objects, filtering by one per parent RFI
def createAMails(mailsReturnedXML : [str], filterTypes : dict) -> list[AconexMail]:
    aMails = []
    prevRef = ""
    for mailXML in mailsReturnedXML:
        mailid = mailXML.get("MailId")
        aMail = AconexMail(mailid=mailid, mailXML=mailXML)

        #if we already have a mail obj for this ref number, exit
        if aMail.refno == prevRef:
            continue

        aMail.setMailType(filterTypes)
        aMail.viewMailMetadata()
        if not aMail.isVoid():
            aMails.append(aMail)
            prevRef = aMail.refno

    return aMails


def getMailsForMailbox(mailbox, luceneQuery) -> str:
    headers = {'Authorization': config.bearer(),
               'Accept': 'application/vnd.aconex.mail.v2+xml'}

    parameters = {"search_type": "PAGED",  # PAGED, meaning return results by "pages" of variable size.
                  "return_fields": "corrtypeid,inreftomailno,docno,subject,fromUserDetails,mailRecipients,sentdate,responsedate,hasAttachments,closedoutdetails",
                  "mail_box": mailbox,  # we must specify a mailbox
                  "search_query": luceneQuery,
                  "page_size": "500",  # TODO handle more pages
                  "sort_field": "responsedate",
                  "sort_direction": "DESC"
                  }

    url = config.projecturl() + "/mail?" + urlencode(parameters)

    xml = getAPIResponse(url, headers, "searching the mailbox")
    return xml


def searchForMail(mailno: str) -> AconexMail:
    luceneQuery = valQuery(mailno)

    filterMails = getMailList(luceneQuery)
    mailDict = dict.fromkeys([m.get("MailId") for m in filterMails])
    assert len(mailDict) == 1  # there should be only one mail with that mail number

    return AconexMail(mailid="",mailXML=filterMails[0])


def valQuery(mailno : str) -> str:
    # this is for orgs with no org code, it breaks the search to have two hyphens
    if mailno[0] == "-":
        return "docno:" + mailno[0] + mailno[1:].replace("-","?")
    elif " " in mailno: #if there is a space in the org code, this will also break
        return "docno:" + mailno.replace(" ", "?")
    else:
        return "docno:" + mailno
