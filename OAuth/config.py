from OAuth.APIcommon import getAPIResponse
from OAuth.MailClasses import AconexMailType
from OAuth.ProjectClasses import Project, projectSelection
from xml.etree import ElementTree as ET

def init(passedBearer, env,  debug=[]):
    global BEARER
    global ACONEXENV
    global PROJECT

    BEARER = passedBearer
    ACONEXENV = env

    global PROJECTURL
    global MAILTYPES

    if debug is None: #if none, then assume no project is required
        PROJECT = None
        PROJECTURL = None
        MAILTYPES = None

    else:
        PROJECT = projectSelection(debug)
        projectname = PROJECT.projectName()
        PROJECTURL = ACONEXENV + "/api/projects/" + PROJECT.projectID()  # url of the chosen project (using project id)
        MAILTYPES = getMailSchema()

def project() -> Project:
    return PROJECT

def bearer() -> str:
    return BEARER

def env() -> str:
    return ACONEXENV

def projecturl() -> str:
    return PROJECTURL

def mailtypes() -> list[AconexMailType]:
    return MAILTYPES

def getMailSchema() -> list[AconexMailType]:
    headers = {'Authorization': bearer(),
               'Accept': 'application/vnd.aconex.mail.v2+xml'}
    url = projecturl() + "/mail/schema/creation"

    xml = getAPIResponse(url=url, headers=headers, explanation="getting the mail creation schema for the project.")
    return getMailTypes(ET.fromstring(xml.strip()))

def getMailTypes(mailSchemaXML) -> [AconexMailType]:
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