import datetime
import webbrowser
from datetime import datetime
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import markdownify

from Setup.APIcommon import getAPIResponse, convertToDateTime, SelLogIn, loadCookies, session, writeCookies
from Setup.Directory import AconexUser
from Setup.FormField import AconexFormField
from Setup.Project import Project

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

class MailFormField(AconexFormField):
    def __init__(self, label, fid, datatype, mandatorystr, value=None):
        mandatory : bool = False if mandatorystr in ["false", "NOT_MANDATORY", "CONDITIONAL"] else True
        super().__init__(label, fid, datatype, mandatory, value)

    def isSearchable(self) -> bool:
        if self.__isSearchable is None:
            pass #TODO
        return self.__isSearchable

class AconexMailType:
    def __init__(self, typeID, typeName, config):
        self.__typeID : str = typeID
        self.__typeName : str = typeName
        self.__projectFields : list[MailFormField] = None
        self.config : config.Config = config

    def __eq__(self, other):
        return self.__typeID == other.__typeID

    def __hash__(self):
        return hash(self.__typeID)

    def corrtypeid(self) -> str:
        return self.__typeID

    def typename(self) -> str:
        return self.__typeName

    def projectfields(self) -> list[tuple]:
        if self.__projectFields is None:
            return []
        else:
            return list(map(lambda pf: (pf.label(), pf.datatype(), pf.isMandatory()), self.__projectFields))

    def debug(self) :
        print(self.__typeName)

    #Use API to get schema for the mail type's form field
    def getFormFields(self, fflink : str):
        self.__projectFields = []
        headers = {'Authorization': self.config.bearer(),
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}

        url = self.config.env() + fflink
        xml = getAPIResponse(url=url, headers=headers, explanation="getting the form fields for the specified mail.")

        formFieldsXml = ET.fromstring(xml.strip()).findall('MailFormField')
        for ffXML in formFieldsXml:
            label = ffXML.find('Label').text
            dtype = ffXML.get('type')
            fid = ffXML.get('identifier')
            mandatory = ffXML.get('mandatory')
            self.__projectFields.append(MailFormField(label, fid, dtype, mandatory))

    #since get mail schema only does create mails, get the replies/forwards of this type and return the xml list
    def getReplySchema(self) -> set[ET.Element]:
        #get replies for this mail type ID
        url = "{purl}/mail/{mailid}/schema/reply".format(purl=self.config.projecturl(), mailid=self.__typeID)
        headers = {'Authorization': self.config.bearer(),
               'Accept': 'application/vnd.aconex.mail.v2+xml'}

        xml = getAPIResponse(url=url, headers=headers, explanation="getting the reply schema for the mail type.")
        if xml is not None:
            mtfXML = ET.fromstring(xml.strip()).find("./MultiValueSchemaField/./[Identifier='MailTypeId']")
            replymailTypesXML = mtfXML.findall("SchemaValues/SchemaValue")
        else:
            self.config.logger.error("Could not get reply schema for the mail type %s."  % self.__typeName)
            replymailTypesXML = []

        #get forwards
        url.replace("reply", "forward")
        xml = getAPIResponse(url=url, headers=headers, explanation="getting the forward schema for the mail type.")
        if xml is not None:
            mtfXML = ET.fromstring(xml.strip()).find("./MultiValueSchemaField/./[Identifier='MailTypeId']")
            forwardmailTypesXML = mtfXML.findall("SchemaValues/SchemaValue")

        else:
            self.config.logger.error("Could not get forward schema for the mail type %s." % self.__typeName)
            forwardmailTypesXML = []

        return set(replymailTypesXML + forwardmailTypesXML)


class AconexMail():
    def __init__(self, config, mailid="", mailXML : ET.Element=None, comments=""):
        self.config: config.Config = config
        self.mailno : str = None

        if mailXML == None: #if list mail hasn't been run
            self.mailid = mailid
            self.viewMailMetadata() #now we will have a mailno
            if self.mailno.startswith("DRAFT"): #sometimes - when getting a mail thread, it will have picked up a draft. if so, exit asap
                self.privateNote = "HBVoid"
                return
            luceneQuery = valQuery(self.mailno)
            mailXML = getMailList(self.config, luceneQuery)[0]

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

        self.RootMail: AconexMail
        self.getRootMail()

        self.ParentMail: AconexMail
        self.replytype : str #if mail was a reply or a forward to its parent

        self.Replies : list[(AconexMail, str)] = []

        self.formfields : list[MailFormField] = []

        self.comments = comments  # the only man-made field

        self.status: str
        self.threadid: str

        self.body: str
        self.privateNote: str = ""

    def __eq__(self, other):
        return self.mailno == other.mailno

    def __lt__(self, other):
        return self.__sentdate < other.__sentdate

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

    #if the final child in the thread (no replies to this mail)
    def isLeaf(self) -> bool:
        return len(self.Replies) == 0

    def debug(self):
        print(self.mailno + ": " + self.subject)

    def setComment(self, comment: str):
        self.comments = comment

    def setMailType(self, filterTypes: dict):
        self.mailType = filterTypes[self.mailtypename]

    def viewMailMetadata(self):
        headers = {'Authorization': self.config.bearer(),
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}
        url = self.config.projecturl() + "/mail/" + self.mailid

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
        return self.privateNote.lower() == "hbvoid"

    def getStatus(self) -> str:
        if self.status == "Partial":
            return "Responded"
        else:
            return self.status

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
            ident = ffXML.get("Identifier")
            dtype = ffXML.get('type')
            mandatory = ffXML.get("mandatory")
            value = ffXML.find("Value").text
            self.formfields.append(MailFormField(label, ident, dtype, mandatory, value))

    # using the label name of the form field, return its value
    def getFormFieldVal(self, label : str) -> str:
        ffvals = [ff.value() for ff in self.formfields if ff.label() == label]
        if len(ffvals) == 1:
            return ffvals[0]
        return None

    def getHyperlink(self) -> str:
        return (self.config.env() + "/hub/index.html?mainTarget=%2FViewCorrespondence%3FPROJECT_ID%3D" + self.config.project().projectID() +
                "%26CORRESPONDENCE_MAILBOX%3D0%26Correspondence_ID%3D" + self.mailid)

    def getSearchHyperlink(self) -> str:
        return ("{env}}/hub/index.html?mainTarget=%2Frsrc%2F20260210.0601%2Fen_AU_DOC%2FmailSearch%2FCorrespondenceSearch.html%3Fmailbox%3DALLBOX%26moduleKey%3DCORRESPONDENCE%26projectId%3D{pid}}rawQueryText%3D{ref}".format(
            env=self.config.env(), pid=self.config.project().projectID(), ref=self.refno
        ))

    def getRootMail(self):
        if self.isRoot():
            self.RootMail = None #this is the root
        else:
            self.RootMail = searchForMail(self.config, self.refno)

        return self.RootMail

    def getMailThread(self):
        self.Replies = []
        #call getMaiLThread
        headers = {'Authorization': self.config.bearer(),
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}
        url = self.config.projecturl() + "/mail/" + self.threadid + "/thread"
        xml = getAPIResponse(url, headers, "getting the mail thread for " + self.mailno)

        # filter to where we currently are in the thread, to prevent an endless loop - we just want this mail's replies/forwards
        threadXML = ET.fromstring(xml.strip()).findall("Mail")

        replyMailsXML = readThread(threadXML, self.mailid)
        replyMailsXML = replyMailsXML.findall("Replies/Mail")

        for rpMXML in replyMailsXML:
            mailid = rpMXML.get("MailId")
            repMail = AconexMail(self.config, mailid=mailid, mailXML=None)
            repType : str = rpMXML.find("ReplyType").text
            if not repMail.isVoid():
                self.Replies.append((repMail,repType))

    def getLatestReply(self):
        if self.isLeaf():
            return None

        repmails, _ = zip(*self.Replies)
        return sorted(repmails, key=lambda rm : rm.__sentdate, reverse=True)[0]


    def getFromOrg(self) -> str:
        return self.From.org()

    def getFromUser(self) -> str:
        return self.From.name()

    def getToOrgs(self) -> [str]:
        return list(set([to.org() for to in self.toUsers if to.wasSentTo()]))

    #get each org the action is with - group client orgs together
    def getBallInCourt(self) -> [str]:
        return self.getToOrgs()

    def getDateTimeSent(self) -> str:
        return datetime.strftime(self.__sentdate, "%d/%m/%Y %H:%M")

    def getClosedOutDate(self) -> str:
        if self.closedoutDate:
            return datetime.strftime(self.closedoutDate, "%d/%m/%Y %H:%M")
        else:
            return ""


class AconexThread:
    def __init__(self, config, threadid: str):
        self.config = config
        self.threadid: str = threadid
        self.threadlist : list[AconexMail] = None
        self.getMailThread()
        self.root = self.getRoot()
        self.latestmail = self.getLatestMail(self.threadlist)

    def getMailThread(self):
        #call getMaiLThread
        headers = {'Authorization': self.config.bearer(),
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}
        url = self.config.projecturl() + "/mail/" + self.threadid + "/thread"
        xml = getAPIResponse(url, headers, "getting the mail thread")
        threadXML = ET.fromstring(xml.strip()).findall("Mail")
        self.threadlist = self.readThread(threadXML)

    #Recursive
    def readThread(self, threadXML: list[ET.Element]) -> list[AconexMail]:
        threadmails : list[AconexMail] = []

        if len(threadXML) > 0:
            for mailXML in threadXML:
                mailid = mailXML.get("MailId")
                replytype = mailXML.find("ReplyType").text
                amail = AconexMail(self.config, mailid=mailid, mailXML=None)
                if not amail.isVoid():
                    amail.replyType = replytype
                    if replytype != "NEVER_RESPONDED":
                        #TODO thats not right
                        pass
                        #parentid = mailXML.find("InRefTo").get("MailId")
                        #amail.ParentMail = self.findfromID(parentid)

                    amail.viewMailMetadata()
                    threadmails.append(amail)

                newthreadXML = mailXML.findall("Replies/Mail")
                if len(newthreadXML) > 0:
                    threadmails += self.readThread(newthreadXML)

            return threadmails
        else:
            return []

    def findfromID(self, mailid) -> AconexMail:
        amails = list(filter(lambda m: m.mailid == mailid, self.threadlist))
        assert len(amails) == 1
        return amails[0]

    def getRoot(self) -> AconexMail:
        if not self.threadlist:
            raise Exception("Thread of mails not created")

        rootmails = list(filter(lambda m: m.isRoot(), self.threadlist))
        rootmails = sorted(rootmails, reverse=True)
        return rootmails[0]

    #return the last valid child mail of the thread
    def getLatestMail(self, maillist : list[AconexMail]) -> AconexMail:
        if not maillist:
            raise Exception("Thread of mails not created")

        #nasty solution - whichever mail has the highest mailid should be the latest
        amailsbyID = sorted(maillist, key=lambda m: m.mailid, reverse=True)

        return amailsbyID[0]

    def getLatestofTypes(self, mtypes : list[AconexMailType]) -> AconexMail:
        typenames = [mt.typename() for mt in mtypes]
        filteredlist = list(filter(lambda m: m.mailtypename in typenames, self.threadlist))
        if len(filteredlist) == 0:
            return None
        else:
            return self.getLatestMail(filteredlist)

EMTEMPLATEPATH = r"C:\Users\nicole.millinship\OneDrive - Henry Brothers Ltd\CLP - Docs\General\#Other Files\Aconex\emails"

#Abstract


def getThisMail(threadXML: [ET.Element], mailid: str) -> ET.Element:
    thisMailXML = list(filter(lambda m: m.get("MailId") == mailid, threadXML))
    if len(thisMailXML) != 0:
        return thisMailXML[0]

    for mailXML in threadXML:
        newthreadXML = mailXML.findall("Replies/Mail")
        if len(newthreadXML) > 0:
            foundMail = readThread(newthreadXML, mailid)
            if foundMail is not None:
                return foundMail

def readThread(threadXML: [ET.Element], mailid: str) -> ET.Element:
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

def getProjectInviteMailID(mailtypes: list[AconexMailType]) -> str:
    # Advice mail type is for HB Test
    projectInviteMail = list(filter(lambda mt: mt.typename() in ["Project Invitation", "Advice"], mailtypes))
    return projectInviteMail[0].corrtypeid()

def getRFIMailTypes(project : Project, mailTypes: list[AconexMailType])  -> (list[AconexMailType], list[AconexMailType]):
    ptypes, rtypes = project.getRFISetup()[1], project.getRFIReplySetup()[1]
    ptypesfound = list(filter(lambda mt: mt.typename() in ptypes, mailTypes))
    rtypesfound = list(filter(lambda mt: mt.typename() in rtypes, mailTypes))
    return ptypesfound, rtypesfound

def getEWNMailTypes(project : Project, mailTypes: list[AconexMailType]) -> (list[AconexMailType], list[AconexMailType]):
    ptypes, rtypes = project.getEWNSetup()
    ptypesfound = list(filter(lambda mt: mt.typename() in ptypes, mailTypes))
    rtypesfound = list(filter(lambda mt: mt.typename() in rtypes, mailTypes))
    return ptypesfound, rtypesfound

def convertMailTypesToDict(mailTypes: list[AconexMailType]) -> dict[str, AconexMailType]:
    filterDict = {mt.typename(): mt for mt in mailTypes}
    return filterDict

def getAllMail(config, mailTypes: list[AconexMailType], params : str = "") -> list[AconexMail]:
    corrTypesIDs = [mType.corrtypeid() for mType in mailTypes]
    luceneQuery = "matchAll:1 NOT HBVoid AND (corrtypeid:" + " OR corrtypeid:".join(corrTypesIDs) + ")" #this will help knock off some void ones
    if params != "":
        luceneQuery = luceneQuery + " AND " + params

    return searchMail(config, luceneQuery, mailTypes)

def searchMail(config, luceneQuery: str, mailTypes: list[AconexMailType]) -> list[AconexMail]:
    mailsReturnedXML = getMailList(config, luceneQuery)

    # sort by ref number, then by earliest of that ref number. i want only one mail per ref number - and i want the 'parent'
    # this would break if a rfi was forwarded twice from one non-rfi parent - like from a transmittal, two rfis were forwarded off it. i am hoping this doesn't happen so it's okay
    # * -1 = sort descending
    mailsReturnedXML = sorted(mailsReturnedXML, key=lambda mail: (mail.find("ReferenceNumber").text,
                                                                  convertToDateTime(mail.find("SentDate").text)))
    mtDict = convertMailTypesToDict(mailTypes)

    filterMails = createAMails(config, mailsReturnedXML, mtDict)

    return filterMails


def getrfithread(project: Project, filterMails : list[AconexMail], mtDict)-> list[dict]:
    # We now have all the RFI mails, we need to figure out the threads
    allRows = []

    for rfimail in filterMails:
        thisRow = {}
        thisRow["Latest Correspondence"] = rfimail.mailno
        if rfimail.isRoot():
            thisRow["Reference Number"] = rfimail.mailno
        # if the 'rfi' mail was not the start of the thread
        else:
            thisRow["Reference Number"] = rfimail.RootMail.mailno

        rfimail.setMailType(mtDict)  # set the AconexMaiLType object
        thisRow["Subject"] = rfimail.subject
        thisRow["Originally From"] = rfimail.getFromOrg()
        thisRow["Date RFI Sent"] = rfimail.getDateTimeSent()
        thisRow["(Helper) Hyperlink"] = rfimail.getHyperlink()
        thisRow["Comments"] = rfimail.comments
        thisRow["RFI Description"] = rfimail.getFormFieldVal(project.getRFISetup()[0])
        thisRow["Discipline(s)"] = rfimail.getFormFieldVal(
            project.getRFIDiscSetup())  # it might not actually have one if it's a sc rfi, but try anyway
        thisRow["RFI Response"] = ""  # nothing for now
        thisRow["Date RFI Responded"] = ""
        thisRow["Ball in Court"] = ""
        thisRow["Status"] = ""  # for now
        thisRow["Date Closed"] = rfimail.getClosedOutDate()

        # if RFI not replied to
        if not rfimail.Replies:
            thisRow["Status"] = rfimail.status
            getBallInCourt(rfimail, allRows, thisRow)
            allRows.append(thisRow)
        else:
            replies = rfimail.Replies
            getReplies(project, rfimail, replies, allRows, thisRow)  # allRows will be auto updated because the dict is a pointer

    return allRows


# the ball in court is everyone who it was sent to who hasn't replied, so add a new row for each org
def getBallInCourt(mail: AconexMail, allRows, thisRow):
    toOrgs = mail.getBallInCourt()
    thisRow["Ball in Court"] = toOrgs[0]

    # if more than one org, create new rows for each. otherwise just return thisRow with the BoC
    for org in toOrgs[1:]:
        firstRow = thisRow.copy()
        firstRow["Ball in Court"] = org
        allRows.append(firstRow)

def getReplies(project : Project, ogMail, replies, allRows, thisRow):
    for replyMail, mRType in replies:
        thisRow["Latest Correspondence"] = replyMail.mailno
        replyMail.viewMailMetadata()  # ensure mail metadata and replies are loaded
        if mRType == "REPLY":
            # if rfi reply mail type
            if replyMail.mailtypename in project.getRFIReplySetup()[1]:
                thisRow["Discipline(s)"] = replyMail.getFormFieldVal(project.getRFIDiscSetup())
                thisRow["RFI Response"] = replyMail.getFormFieldVal(project.getRFIReplySetup()[0])
                thisRow["Date RFI Responded"] = replyMail.getDateTimeSent()
                thisRow["Status"] = ogMail.status

                # if it's not marked as closed out, the ball in court is the sender, who needs to reply or close out
                thisRow["Ball in Court"] = "N/A" if ogMail.isClosed() else ogMail.getFromOrg()

            # if a gc / other mail type
            else:
                if replyMail.isOutstanding():  # if this gc is awaiting a response
                    thisRow["Status"] = replyMail.status
                    getBallInCourt(replyMail, allRows, thisRow)
                    thisRow["Comments"] = replyMail.body  # this might not be the best way of doing it

        elif mRType == "FORWARD":
            # if fwded as rfi
            if replyMail.mailtypename in project.getRFISetup()[1]:
                thisRow["RFI Description"] = replyMail.getFormFieldVal(project.getRFISetup()[0])
                thisRow["Date RFI Sent"] = replyMail.getDateTimeSent()
                thisRow["Discipline(s)"] = replyMail.getFormFieldVal(project.getRFIDiscSetup())
                thisRow["RFI Response"] = ""  # nothing for now
                thisRow["Date RFI Responded"] = ""

                # if fwded RFI not replied to
                if not replyMail.Replies:
                    thisRow["Status"] = replyMail.status
                    getBallInCourt(replyMail, allRows, thisRow)

            # if fwded as response to rfi
            if replyMail.mailtypename in project.getRFIReplySetup()[1]:
                thisRow["RFI Response"] = replyMail.getFormFieldVal(project.getRFIReplySetup()[0])
                thisRow["Date RFI Responded"] = replyMail.getDateTimeSent()
                thisRow["Status"] = "Responded"
                thisRow["Ball in Court"] = ogMail.getFromOrg()

            # if fwded as gc / other mail
            else:
                if replyMail.isOutstanding():  # if this gc is awaiting a response
                    thisRow["Status"] = replyMail.status
                    getBallInCourt(replyMail, allRows, thisRow)
                    thisRow["Comments"] = replyMail.body  # this might not be the best way of doing it

        rmReplies = replyMail.Replies

        if len(rmReplies) > 0:
            newRow = thisRow.copy()
            getReplies(project, replyMail, rmReplies, allRows, newRow)

        else:
            allRows.append(thisRow)

# wrapper to search the inbox and the sent box
def getMailList(config, luceneQuery) -> [str]:
    iXML = getMailsForMailbox(config,"inbox", luceneQuery)  # in inbox
    sXML = getMailsForMailbox(config,"sentbox", luceneQuery)  # in sent box
    return ET.fromstring(iXML.strip()).findall("SearchResults/Mail") + ET.fromstring(sXML.strip()).findall(
        "SearchResults/Mail")

# Convert mail xml to Aconex Mail objects, filtering by one per parent RFI
def createAMails(config, mailsReturnedXML: [str], filterTypes: dict) -> list[AconexMail]:
    aMails = []
    prevRef = ""
    for mailXML in mailsReturnedXML:
        mailid = mailXML.get("MailId")
        aMail = AconexMail(config=config, mailid=mailid, mailXML=mailXML)

        # if we already have a mail obj for this ref number, exit
        if aMail.refno == prevRef:
            continue

        aMail.setMailType(filterTypes)
        aMail.viewMailMetadata()
        if not aMail.isVoid():
            aMails.append(aMail)
            prevRef = aMail.refno

    return aMails

def getMailsForMailbox(config, mailbox, luceneQuery) -> str:
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

def searchForMail(config, mailno: str) -> AconexMail:
    luceneQuery = valQuery(mailno)

    filterMails = getMailList(config, luceneQuery)
    mailDict = dict.fromkeys([m.get("MailId") for m in filterMails])
    assert len(mailDict) == 1  # there should be only one mail with that mail number

    return AconexMail(config, mailid="", mailXML=filterMails[0])

def valQuery(mailno: str) -> str:
    #escape brackets in mail no
    mailno = mailno.translate(str.maketrans({'(': "\\(", ")": "\\)", '+': '\\+'}))
    # this is for orgs with no org code, it breaks the search to have two hyphens
    if mailno[0] == "-":
        return "docno:" + mailno[0] + mailno[1:].replace("-", "?")
    elif " " in mailno or "." in mailno:  # spaces and periods break it completely, replace with ?
        return "docno:" + mailno.translate(str.maketrans({".": "?", " ": "?"}))
    else:
        return "docno:" + mailno


def openDraftLink(config, returnedXml):
    draftedMailId = ET.fromstring(returnedXml.strip()).find('NewMailId').text

    draftMailURL = config.env() + "/rsrc/20250422.1347/en_AU_DOC/mail/view/index.html#/" + config.project().projectID() + "/" + draftedMailId
    config.info("Opening link...")
    webbrowser.open(draftMailURL)

#Absolute BS you cannot just send a transmittal you can only draft
def sendDraft(config, draftMailURL):
    url = "{env}internal/projects/{pid}/users/{uid}/mails/DRAFTBOX".format(env=config.env(), pid=config.project().projectID(), uid=config.project().getMyUserID()) #https://ea1.aconex.com/internal/projects/1879048648/users/1879050797/mails/DRAFTBOX?pageNo=1&sortDirection=DESC&sortField=sentdate"
    cookies, cj = loadCookies(config)

    jsonRes = session.get(draftMailURL, headers=None, cookies=cj, allow_redirects=False)
    print(jsonRes.text)
    if jsonRes.status_code == 404 or cookies is None:
        cookies, cj = SelLogIn(config)

    driver = webdriver.Edge()

    driver.get(config.env())

    for cookie in cookies:
        print(cookie)
        driver.add_cookie(cookie)

    driver.get(draftMailURL)

    wait = WebDriverWait(driver, 60).until(EC.new_window_is_opened(driver.window_handles))
    driver.quit()