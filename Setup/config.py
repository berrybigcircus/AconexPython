import datetime
import logging
import os
import pathlib
import sys
import time

if sys.platform == "win32":
    import pywintypes

from Setup.APIcommon import getAPIResponse
from Setup.Doc import DocFormField
from Setup.Mail import AconexMailType, MailFormField
from Setup.Project import Project, projectSelection
from xml.etree import ElementTree as ET

FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
def createlogger():
    lformat = logging.Formatter(fmt="{asctime}: {levelname}: {message}", style="{", datefmt="%Y-%m-%d %H:%M")

    logger: logging.Logger = logging.getLogger('aconexlogger')
    logger.setLevel(logging.DEBUG)

    #write to file unlesss CI
    if not os.getenv("CI"):
        logpath = FOLDERPATH + "/Logs/debug.log"
        mode = "a" if os.path.exists(logpath) else "w"
        file_handler = logging.FileHandler(filename=FOLDERPATH + "/Logs/debug.log", mode=mode, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(lformat)
        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(lformat)


    logger.addHandler(console_handler)
    return logger

class Config:
    def __init__(self):
        self.BEARER: str
        self.ACONEXENV: str
        self.TOKEN: str
        self.EApass : str = None
        self.logger: logging.Logger = createlogger()
        self.PROJECT : Project
        self.PROJECTNAME : str
        self.PROJECTURL : str

        self.folderroot = str(pathlib.Path(__file__).parents[1].resolve())

        self.MAILFIELDS : list[MailFormField] = None #the entire mail schema for creating a new mail
        self.MAILTYPES: list[(bool, AconexMailType)] = None  # bool = True if you can start a thread with the mail type
        self.CREATEMAILTYPES: list[AconexMailType] = None

        self.DOCFIELDS : list[DocFormField] = None
        self.DOCSTATUSES : dict = None
        self.DOCTYPES : dict = None

    def create(self, passedBearer, env,  debug=[], token=None):
        self.BEARER = passedBearer
        self.ACONEXENV = env
        self.TOKEN = token

        if debug is None:  # if none, then assume no project is required
            self.PROJECT = None
            self.PROJECTURL = None
        else:
            self.PROJECT = projectSelection(debug)
            self.PROJECTNAME = self.PROJECT.projectName()
            self.PROJECTURL = self.ACONEXENV + "/api/projects/" + self.PROJECT.projectID()  # url of the chosen project (using project id)

    def setPass(self, spass: str):
        self.EApass = spass

    def getPass(self):
        return self.EApass

    def projectname(self) -> str:
        return self.PROJECTNAME

    def projecturl(self) -> str:
        return self.PROJECTURL

    #Logger overriding functions
    def info(self, msg : str):
        if self.logger:
            self.logger.info(msg)

    def warning(self, msg : str):
        if self.logger:
            self.logger.warning(msg)

    def error(self, msg : str):
        if self.logger:
            self.logger.error(msg)

    def debug(self, msg : str):
        if self.logger:
            self.logger.debug(msg)

    def project(self) -> Project:
        return self.PROJECT

    def bearer(self) -> str:
        return self.BEARER

    def env(self) -> str:
        return self.ACONEXENV

    def token(self) -> str:
        return self.TOKEN

    def getOutlookLastRanLocation(self) -> str:
        return "{}\\Setup\\outlookLastRan.txt".format(self.folderroot)

    def getOrgCSVLocation(self) -> str:
        return r"C:\Users\nicole.millinship\OneDrive - Henry Brothers Ltd\CLP - Docs\General\#Other Files\Aconex\OrgAdminList.csv"

    def getNUTrackerLocation(self) -> str:
        return r"C:\Users\nicole.millinship\OneDrive - Henry Brothers Ltd\CLP - Docs\General\#Other Files\Aconex\Aconex New Users Tracker.xlsm"

    def mailtypes(self) -> list[AconexMailType]:
        if not self.MAILTYPES:
            initialmailtypes : list[(bool,AconexMailType)] = list(map(lambda e: (True, e), self.create_mailtypes()))
            headers = {'Authorization': self.bearer(),
                       'Accept': 'application/vnd.aconex.mail.v2+xml'}

            # Because the create mail schema doesnt include all the reply types, the search schema has corrtypeid, and the list of valid IDs/Type Names
            url = self.projecturl() + "/mail/schema/search"
            xml = getAPIResponse(url=url, headers=headers,
                                 explanation="getting the mail search schema for the project.")

            mtfXML = ET.fromstring(xml.strip()).find(
                "./MultiValueSchemaField/./[Identifier='corrtypeid']")  # find the field for mail types
            mailTypesXML: set[ET.Element] = set(mtfXML.findall("SchemaValues/SchemaValue"))

            createmailtypesIDS = [mt.corrtypeid() for mt in self.create_mailtypes()]
            newmailtypesXML = set(filter(lambda elem: elem.find('Id').text not in createmailtypesIDS, mailTypesXML))

            self.MAILTYPES = initialmailtypes + list(map(lambda e: (False, e), self.getMailTypes(newmailtypesXML)))

        return list(zip(*self.MAILTYPES))[1]

    def mailschema(self):
        headers = {'Authorization': self.bearer(),
                   'Accept': 'application/vnd.aconex.mail.v2+xml'}

        url = self.projecturl() + "/mail/schema/creation"
        xml = getAPIResponse(url=url, headers=headers,
                             explanation="getting the mail creation schema for the project.")

        schemaxml = ET.fromstring(xml.strip())
        root = ET.ElementTree(schemaxml).getroot()

        self.MAILFIELDS = []

        for fieldxml in root:
            if fieldxml.tag == "MailTypes":
                continue
            label = fieldxml.find('FieldName').text
            fid = fieldxml.find('Identifier').text
            dt = fieldxml.find('DataType').text
            mandatorystr = fieldxml.find('Attributes/EntityField').attrib['MandatoryStatus']
            mailfield = MailFormField(label, fid, dt, mandatorystr)
            schemavals = fieldxml.findall("SchemaValues/SchemaValue")
            if schemavals:
                mailfield.setSelectionList(schemavals)

            if fid == "MailTypeId":
                mailTypesXML: set[ET.Element] = set(schemavals)
                self.CREATEMAILTYPES = list(self.getMailTypes(mailTypesXML))

            self.MAILFIELDS.append(mailfield)

    def mailfields(self):
        if not self.MAILFIELDS:
            self.mailschema()

        return self.MAILFIELDS

    def mandatorymailfields(self) -> list[MailFormField]:
        return list(filter(lambda mf: mf.isMandatory(), self.mailfields()))

    def create_mailtypes(self) -> list[AconexMailType]:
        if not self.CREATEMAILTYPES:
            self.mailschema()

        return self.CREATEMAILTYPES


    def getMailTypes(self, mailTypesXML : set[ET.Element]) -> set[AconexMailType]:
        mail_types : set[AconexMailType] = set()

        for elem in mailTypesXML:
            typeName = elem.find('Value').text
            if typeName != "Email":
                m = AconexMailType(typeID=elem.find('Id').text, typeName=typeName, config=self)
                mail_types.add(m)

                #TODO - this will only work for create mail schemas, only create mail schema has the link to the form fields
                ffLink = elem.find(
                    'Links/Link')  # link to api request that will give you the details for the form fields for that mail type
                if ffLink is not None:
                    m.getFormFields(ffLink.get('href'))

        return mail_types

    def docfields(self):
        if not self.DOCFIELDS:
            self.DOCFIELDS = []
            url = config.projecturl() + "/register/schema"
            headers = {'Authorization': self.bearer()}

            schemaxml = getAPIResponse(url=url, headers=headers,
                                 explanation="getting the document schema for the project.")

            #this is the list of fields to create / revise a document
            creationxml = ET.fromstring(schemaxml.strip()).findall("./EntityCreationSchemaFields/")

            #this is the list of fields that can be searched on
            searchxml = ET.fromstring(schemaxml.strip()).findall("./SearchSchemaFields/")

            for creationfield in creationxml:
                label = creationfield.find('FieldName').text
                fid = creationfield.find('Identifier').text
                dt = creationfield.find('DataType').text

                mandatorystr = creationfield.find('Attributes/EntityField').attrib['MandatoryStatus']

                docfield = DocFormField(label, fid, dt, mandatorystr)

                searchequiv = list(filter(lambda sf : sf.find('FieldName').text == label, searchxml))#searchxml.find('./[FieldName={}').format(label)
                docfield.setSearchable(len(searchequiv) == 1)

                schemavals = creationfield.findall("SchemaValues/SchemaValue")
                if schemavals:
                    docfield.setSelectionList(schemavals)

                self.DOCFIELDS.append(docfield)

        return self.DOCFIELDS

    def searchForFormField(self, fieldname) -> DocFormField:
        ffs = list(filter(lambda df: df.label() == fieldname, self.docfields()))
        if ffs:
            return ffs[0]

        else:
            config.logger.warning("No form field found called %s" % fieldname)
            return None

    def mandatorydocfields(self) -> list[DocFormField]:
        return list(filter(lambda df: df.isMandatory(), self.docfields()))

    #standard form field with a Name and ID only
    def formfieldidsandvals(self, fieldname) -> dict:
        tempdict = {}
        formfield: DocFormField = self.searchForFormField(fieldname)

        for dt in formfield.selectionXML:
            v = dt.find('Value').text
            i = dt.find('Id').text
            tempdict[v] = i

        return tempdict

    def docStatuses(self) -> dict:
        if not self.DOCSTATUSES:
            self.DOCSTATUSES = self.formfieldidsandvals(fieldname='Status')

        return self.DOCSTATUSES

    def docTypes(self) -> dict:
        if not self.DOCTYPES:
            self.DOCTYPES = self.formfieldidsandvals(fieldname = 'Type')

        return self.DOCTYPES

config : Config = Config()

def init(passedBearer, env,  debug=[], token=None):
    global config

    if not config:
        config = Config()
        config.create(passedBearer, env, debug, token)
        config.info("Configured.")

    #init may be run more than once so re-create
    else:
        config.create(passedBearer, env, debug, token)

#get datetime a file was modified
def get_modification_time(filepath) -> str:
    modification_time = os.path.getmtime(filepath)
    readable_time = datetime.datetime.fromtimestamp(modification_time).strftime('%Y/%m/%d %H:%M')
    return readable_time

def refreshTracker(filepath, accept_time_diff : bool = False) -> str:
    MAX_RETRIES = 3
    import win32com.client

    wb: object


    # Check if the date generated timestamp has changed (proves it refreshed)


    attempt = 1
    for attempt in range(1, MAX_RETRIES+1):
        xlapp = win32com.client.DispatchEx("Excel.Application")

        xlapp.DisplayAlerts = False
        xlapp.AskToUpdateLinks = False
        xlapp.EnableEvents = False
        xlapp.Visible = True
        try:
            wb = xlapp.Workbooks.Open(filepath)
        except pywintypes.com_error:
            config.logger.error("Workbook %s not found" % filepath)
            xlapp.Quit()
            del xlapp
            return None
        sheet = wb.Sheets("RawData")
        original_dategen = sheet.Range("B2").Value


        config.logger.info("Attempt %d" % attempt)
        time.sleep(3)
        CONN_RETRIES = 10

        for conn in wb.Connections:
            try:
                conn.OLEDBConnection.BackgroundQuery = False
            except:
                pass

        for _ in range(CONN_RETRIES):
            try:
                wb.RefreshAll()

                break
            except pywintypes.com_error:
                time.sleep(2)

        while True:
            refreshing = False
            for conn in wb.Connections:
                try:
                    if conn.OLEDBConnection.Refreshing:
                        refreshing = True
                except:
                    pass
            if not refreshing:
                break
            time.sleep(1)

        new_dategen = sheet.Range("B2").Value

        if not accept_time_diff and original_dategen == new_dategen:
            config.logger.error("Tracker did not successfully refresh.")
            wb.Close()
            xlapp.Quit()
            continue

        wb.Save()
        wb.Close()
        xlapp.Quit()
        break




    del wb
    del xlapp

    wb = None
    xlapp = None

    config.logger.info("%d, %d" % (attempt, MAX_RETRIES))

    if int(attempt) < int(MAX_RETRIES):
        if type(new_dategen) != str:
            new_dategen = new_dategen.strftime("%Y/%m/%d %H:%M")
        return new_dategen
    else:
        return None


