from OAuth.MailClasses import AconexMailType
from OAuth.ProjectClasses import Project, projectSelection

def init(passedBearer, env,  project: Project = projectSelection(True)):
    global BEARER
    global ACONEXENV
    global PROJECT

    BEARER = passedBearer
    ACONEXENV = env
    PROJECT = project
    projectname = PROJECT.projectName()

    global PROJECTURL
    PROJECTURL = "https://api.aconex.com/api/projects/" + PROJECT.projectID()  # url of the chosen project (using project id)

    global MAILTYPES
    MAILTYPES = PROJECT.getMailSchema(PROJECTURL, BEARER)

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