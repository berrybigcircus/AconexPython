import win32com.client

from connectToOutlook import connect, find_folder, initProject, OutlookConfig
from Setup.config import config

def main():
    outlookconfig : OutlookConfig = OutlookConfig(debug=False)
    outlook = connect()

    registerfolder : object = find_folder("to register", outlook)

    #each project has its own subfolder with the emails to register in
    for folder in registerfolder.Folders:
        if folder.name == "000":
            projectname = "HBC Office"
            initProject(outlookconfig, projectname, "projectnames")
        else:
            project_code = folder.name
            initProject(outlookconfig, project_code, "projectcodes")

        #Check for excel mail template
        print(config.project().getMailTemplateLocation())