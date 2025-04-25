from datetime import datetime
import pandas
import markdownify #to convert mail body from html to markdown

from OAuth.APIcommon import getAPIResponse, projectSelection, Project
import xml.etree.ElementTree as ET #for parsing xml
from urllib.parse import urlencode

mailData = {
    "Status": [],
    "Ball in Court": [],
    "Reference Number": [],
    "Subject": [],
    "Originally From": [],
    "RFI Description": [],
    "Discipline(s)": [],
    "Date Sent": [],
    "RFI Response": [],
    "Latest Correspondence": [],
    "Comments": []
}

class AconexFormField():
    def __init__(self, label, fid, value=None):
        self.__label : str = label
        self.__identifier : str = fid
        self.__value : str = value

    def debug(self):
        print(self.__identifier)

class AconexMailType():
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
        headers = {'Authorization': bearer,
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}

        url = aconexEnv + fflink
        xml = getAPIResponse(url=url, headers=headers, explanation="getting the form fields for the specified mail.")
        print(xml)

        formFieldsXml = ET.fromstring(xml.strip()).findall('MailFormField')
        for ffXML in formFieldsXml:
            label = ffXML.find('Label')
            fid = ffXML.get('identifier')
            self.__projectFields.append(AconexFormField(label.text, fid))

    #def getFormFieldsValue(self):

class AconexUser():
    def __init__(self, name, org, disttype):
        self.__name = name
        self.__org = org
        self.__disttype = disttype

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
            luceneQuery = valQuery(self.mailno)
            iXML, sXML = getMailList(luceneQuery)

            totalResultsInbox = int(ET.fromstring(iXML.strip()).get("TotalResults"))

            if totalResultsInbox > 0:
                mailXML = ET.fromstring(iXML.strip()).find("SearchResults/Mail")
                print(mailXML)
            else: #if no results from inbox, assume it was found in sent box instead
                mailXML = ET.fromstring(sXML.strip()).find("SearchResults/Mail")

        else:
            self.mailno = mailXML.find("MailNo").text
            self.mailid = mailXML.get("MailId")


        self.refno =  mailXML.find("ReferenceNumber").text
        self.subject = mailXML.find("Subject").text
        self.hasAttach(mailXML.find("HasAttachments").text)
        self.responsereqDate(mailXML.find("ResponseRequired/ResponseRequiredDate"))
        self.sentDate(mailXML.find("SentDate").text)

        self.mailtypename = mailXML.find("CorrespondenceType").text

        recipientsXML = mailXML.findall("ToUsers/Recipient")
        toUsers = []
        for recXML in recipientsXML:
            name = recXML.find("Name").text
            organisation = recXML.find("OrganizationName").text
            disttype = recXML.find("DistributionType")
            toUsers.append(AconexUser(name, organisation, disttype))
        self.toUsers = toUsers

        fromuserXML = mailXML.find("FromUserDetails")
        fromname = fromuserXML.find("Name").text
        fromorg = fromuserXML.find("OrganizationName").text
        self.From = AconexUser(fromname, fromorg, "FROM")

        self.mailtype : AconexMailType

        self.hyperlink: str = self.getHyperlink()  # as per usual i have to write it myself SMH

        self.isRoot: bool  # if the ref number is this mail - then it is the start of thread
        self.RootMail: AconexMail
        self.getRootMail()

        self.Replies: list[AconexMail] = []

        self.comments = comments  # the only man-made field

        self.status: str
        self.threadid: str
        self.body: str
        self.privateNote: str = ""

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

    def mailType(self, filterTypes: dict):
        self.mailType = filterTypes[self.mailtypename]

    def viewMailMetadata(self):
        headers = {'Authorization': bearer,
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}
        url = PROJECTURL + "/mail/" + self.mailid

        xml = getAPIResponse(url, headers, "getting mail metadata for mail id: " + self.mailid)

        root = ET.fromstring(xml.strip())

        #if it has not been fed values for these already
        if not self.mailno:
            self.mailno = root.find("MailNo").text

        # there can be multiple notes, but since you can't delete - take the last one as the important one (i'm assuming the notes are in date order)
        notes = root.findall("Notes/Note/NoteContents")
        if notes: self.privateNote = notes[-1].text

        self.body = markdownify.markdownify(root.find("MailData").text)
        self.status = root.find("Status").text
        self.threadid = root.find("ThreadId").text
        self.getReplies()

    def isVoid(self) -> bool:
        return (self.privateNote == "HBVoid")

    def getFormFields(self):
        #TODO
        pass
        #self.mailtype.__projectFields.getValue

    def getHyperlink(self) -> str:
        return (aconexEnv + "/hub/index.html?mainTarget=%2FViewCorrespondence%3FPROJECT_ID%3D" + chosenProjectID +
                "%26CORRESPONDENCE_MAILBOX%3D0%26Correspondence_ID%3D" + self.mailid)

    def getRootMail(self):
        if self.isRoot:
            self.RootMail = None #this is the root
        else:
            self.RootMail = searchForMail(self.refno)

        return self.RootMail

    def getReplies(self):
        if self.status == "Responded" or self.status == "Closed-Out":
            self.getMailThread()
        else:
            self.Replies = [] #if it hasn't been responded to, it can't possibly have any replies (probs - unless i implemented it weirdly)

    def getMailThread(self):
        self.Replies = []
        #call getMaiLThread
        headers = {'Authorization': bearer,
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}
        url = PROJECTURL + "/mail/" + self.threadid + "/thread"
        xml = getAPIResponse(url, headers, "getting the mail thread for " + self.mailno)

        replyMailsXML = ET.fromstring(xml.strip()).findall("Mail/Replies/Mail")

        for rpMXML in replyMailsXML:
            mailid = rpMXML.get("MailId")
            repMail = AconexMail(mailid=mailid)
            if not repMail.isVoid():
                self.Replies.append(repMail)

    def getFromOrg(self) -> str:
        return self.__from.org()

    def getDateTimeSent(self) -> str:
        return datetime.strftime(self.__sentdate, "%d/%m/%Y %H:%M")

def main(passedBearer, env, project: Project = projectSelection(True)):
    global bearer
    bearer = passedBearer
    global aconexEnv
    aconexEnv = env

    global projectname
    global chosenProjectID
    projectname, chosenProjectID = project.getProject()
    global RFIMAILTYPENAMES
    RFIMAILTYPENAMES = project.getRFISetup()

    global PROJECTURL
    PROJECTURL = "https://api.aconex.com/api/projects/" + chosenProjectID  # url of the chosen project (using project id)

    global MAILTYPES
    MAILTYPES = getMailSchema()

    filename : str = project.projectCodePrefix()+"RFI Data.xlsx" #for this project, this is where the RFI data is read / written
    importExcel(filename) #TODO - pull these
    getAllMail(getRFIMailTypes(MAILTYPES))
    #exportToExcel(filename)

def getMailSchema() -> list[AconexMailType]:
    headers = {'Authorization': bearer,
               'Accept': 'application/vnd.aconex.mail.v2+xml'}
    url = PROJECTURL + "/mail/schema/creation"

    xml = getAPIResponse(url=url, headers=headers, explanation="getting the mail creation schema for the project.")
    print(xml)
    return getMailTypes(ET.fromstring(xml.strip()))

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

def getRFIMailTypes(mailTypes : list[AconexMailType]) -> list[AconexMailType]:
    return list(filter(lambda mt: mt.typename() in RFIMAILTYPENAMES, mailTypes))

def convertMailTypesToDict(mailTypes : list[AconexMailType]) -> dict[str, AconexMailType]:
    filterDict = {mt.typename(): mt for mt in mailTypes}
    return filterDict

#get all RFI mails
def getAllMail(mailTypes : list[AconexMailType]):
    corrTypesIDs = [mType.corrtypeid() for mType in mailTypes]
    luceneQuery = "corrtypeid:" + " OR corrtypeid:".join(corrTypesIDs)

    iXML, sXML = getMailList(luceneQuery)
    mtDict = convertMailTypesToDict(mailTypes)
    filterMails = createAMails(iXML, mtDict) + createAMails(sXML, mtDict)

    #We now have all the RFI mails, we need to figure out the threads
    thisRow = {}

    for rfiMail in filterMails:
        if rfiMail.isRoot:
            thisRow["Reference Number"] = rfiMail.mailno
            thisRow["Subject"] = rfiMail.subject
            thisRow["Originally From"] = rfiMail.getFromOrg()
            thisRow["Date Sent"] = rfiMail.getDateTimeSent()
            #TODO - hyperlink

            thisRow["RFI Description"] = ""  # todo

        else:
            thisRow = {}
            rootMail = rfiMail.RootMail
            thisRow["Reference Number"] = rootMail.mailno
            if rootMail.mailtype in mailTypes: #if root is a RFI mail
                pass
            else:
                pass


    #print([mail.debug() for mail in filterMails])

#wrapper to search the inbox and the sent box
def getMailList(luceneQuery)  -> (str, str):
    return (getMailsForMailbox("inbox", luceneQuery),  # in inbox
        getMailsForMailbox("sentbox", luceneQuery))  # in sent box

def createAMails(xml : str, filterTypes : dict) -> list[AconexMail]:
    mailsReturnedXML = ET.fromstring(xml.strip()).findall("SearchResults/Mail")
    aMails = []

    for mailXML in mailsReturnedXML:
        mailid = mailXML.get("MailId")
        aMail = AconexMail(mailid=mailid, mailXML=mailXML)
        aMail.mailType(filterTypes)
        aMail.viewMailMetadata()
        if not aMail.isVoid():
            aMails.append(aMail)

    return aMails


def getMailsForMailbox(mailbox, luceneQuery) -> str:
    headers = {'Authorization': bearer,
               'Accept': 'application/vnd.aconex.mail.v2+xml'}

    parameters = {"search_type": "PAGED",  # PAGED, meaning return results by "pages" of variable size.
                  "return_fields": "corrtypeid,inreftomailno,docno,subject,fromUserDetails,mailRecipients,sentdate,responsedate,hasAttachments,closedoutdetails",
                  "mail_box": mailbox,  # we must specify a mailbox
                  "search_query": luceneQuery,
                  "page_size": "500",  # TODO handle more pages
                  "sort_field": "responsedate",
                  "sort_direction": "DESC"
                  }

    url = PROJECTURL + "/mail?" + urlencode(parameters)

    xml = getAPIResponse(url, headers, "searching the mailbox")
    return xml


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
        print(refno)

        am = searchForMail(refno)
        am.setComment(comments)
        aconexMails.append(am)

    [am.debug() for am in aconexMails]
    return aconexMails

def exportToExcel(filename):
    dataframe = pandas.DataFrame(data=mailData)  # convert into pandas data frame for exporting
    with pandas.ExcelWriter(filename,mode='a', if_sheet_exists='replace') as writer: #just paste over everything, it's easier
        dataframe.to_excel(writer,
                           sheet_name="RawData",
                           header= True,
                           startrow = 0,
                           index=False) #no index col
    print("     Mail data added to " + filename)

#Call 'List Mail' for one mail number in particular, and create Mail Object
def searchForMail(mailno: str) -> AconexMail:
    luceneQuery = valQuery(mailno)

    iXML, sXML = getMailList(luceneQuery)
    mtDict = convertMailTypesToDict(MAILTYPES)
    filterMails = createAMails(iXML, mtDict) + createAMails(sXML, mtDict)

    assert len(filterMails) == 1  # there should be only one mail with that mail number
    print(filterMails[0].debug())
    return filterMails[0]

def valQuery(mailno : str) -> str:
    # this is for orgs with no org code, it breaks the search to have two hyphens
    if mailno[0] == "-":
        print("docno:" + mailno[0] + mailno[1:].replace("-","?"))
        return "docno:" + mailno[0] + mailno[1:].replace("-","?")

    else:
        return "docno:" + mailno