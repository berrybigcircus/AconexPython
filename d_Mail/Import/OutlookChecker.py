import os

import pandas

from Setup.Outlook import find_folder, connect, initProject, getEmAddress
from Setup.config import config
from a_NewUser.newUser import filtercontacts
from d_Mail.Import.ImportFromExcel import createTemplate, importExcel

def main():
    outlook = connect()

    registerfolder : object = find_folder("to register", outlook)

    contactsfolder = outlook.GetDefaultFolder(10)
    mycontacts = contactsfolder.Items

    #each project has its own subfolder with the emails to register in
    for folder in registerfolder.Folders:
        if folder.name == "000":
            projectname = "HBC Office"
            initProject(projectname, "projectnames", False)
        else:
            project_code = folder.name
            initProject(project_code, "projectcodes", False)

        #Check for excel mail template
        mailtemplatepath = config.project().getMailTemplateLocation()
        if not os.path.exists(mailtemplatepath):
            createTemplate()
        else:
            config.logger.info("Template exists.")

        sheetname = config.project().getGCMailID()
        gcDF = pandas.read_excel(open(mailtemplatepath, 'rb'), sheet_name=sheetname, skiprows=[0],
                                            engine='openpyxl')

        assert gcDF is not None
        emails = folder.Items
        newRows = pandas.DataFrame(columns=gcDF.columns) #create a set of new rows so it can be appended, in case of existing data
        mailDFDict = dict.fromkeys(gcDF.columns)
        rowid = len(gcDF.index)
        for email in emails:
            rowid += 1
            mailDFDict["RowID*"] = str(rowid)
            mailDFDict["Email EntryID (Leave blank if no email)*"] = email.EntryID
            mailDFDict["To Names (Separate by semi-colon)*"] = concatAddresses(contactsfolder, email.Recipients)
            mailDFDict["Subject*"] = email.Subject
            print(mailDFDict)
            exit()

def concatAddresses(contactsfolder, erecipients) -> str:
    #take list of email recipients/senders
    for i in range(1,erecipients.Count):
        recipient = erecipients.Item(i)
        if not recipient.Resolved:
            recipient.Resolve()
            
        #extract email address
        email = getEmAddress(recipient)

        #lookup in my contacts to see if they have an aconex ID. add to my contacts if they dont exist
        sfilters = ["[Email1Address] = {email}".format(email=email)] #filter on email address
        print(sfilters)
        outlookcontact = filtercontacts(contactsfolder, sfilters, None)
        if outlookcontact.already_exists() and outlookcontact.getaconexid():
            config.logger.info("Existing outlook contact and Aconex user with ID %s" % outlookcontact.getaconexid())

        elif not outlookcontact.already_exists():
            outlookcontact.setemail(email)
            outlookcontact.addToContacts(contactsfolder)