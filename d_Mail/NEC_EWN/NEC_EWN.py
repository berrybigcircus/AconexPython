import datetime
import os
import pathlib

import pandas
from Setup import Project
from Setup.APIcommon import session, getAPIResponse, postAPIResponse
from Setup.config import config
from Setup.Mail import AconexMail, getEWNMailTypes, getAllMail, AconexThread

mailData = {
    "Status": [],
    "Reference Number": [],
    "Subject": [],
    "Description": [],
    "Originally Sent": [],
    "Last updated": [],
    "Risk Severity": [],
    "Risk Likelihood": [],
    "Risk Score": [],
    "Proposed Actions": []
}

def main():
    global FOLDERPATH
    FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
    filename: str = FOLDERPATH + "\\" + config.project().projectCodePrefix() + "EWN Risk Register.xlsx"

    #Get the EW mail type setup for the project (initial parent and reply)
    ewmailtypesp, ewmailtypesr = getEWNMailTypes(config.project(), config.mailtypes())

    ewmails : list[AconexMail] = list(filter(lambda m : not m.isVoid(), getAllMail(config, ewmailtypesp)))
    #TODO - we need to do somtehing about void mails, since we can't read the notes / comments box any more
    for ewn in ewmails:
        ewn.debug()
        ewthread = AconexThread(config, ewn.threadid)

        parentmail = ewthread.root
        latestewnresponse = ewthread.getLatestofTypes(ewmailtypesr)

        ewthread.root.debug()
        latestewnresponse.debug()

        mailData["Reference Number"].append(ewn.mailno)
        mailData["Subject"].append(ewn.subject)
        mailData["Originally Sent"].append(ewn.getDateTimeSent())

        mailData["Description"].append(ewn.getFormFieldVal("Description")) #might not work for every project

        if ewn.mailno != latestewnresponse.mailno:
            pass

        #this is the only mail
        else:
            mailData["Proposed Actions"].append(ewn.getFormFieldVal("Proposed Actions"))

            rseveritystr = ewn.getFormFieldVal("Risk Severity")
            mailData["Risk Severity"].append(rseveritystr)  # might not work for every project
            rlikelihoodstr = ewn.getFormFieldVal("Risk Likelihood")
            mailData["Risk Likelihood"].append(rlikelihoodstr) #might not work for every project
            mailData["Risk Score"].append(getriskscore(rseveritystr, rlikelihoodstr))

            mailData["Last updated"].append(getlastupdatedetails(ewn))


def getriskscore(rseveritystr, rlikelihoodstr) -> str:
    try:
        score = int(rseveritystr) + int(rlikelihoodstr)
        return str(score)
    except ValueError:
        config.logger.error("Couldn't calculate risk score from values %s, %s" % (rseveritystr, rlikelihoodstr))
        return ""

def getlastupdatedetails(ewn: AconexMail) -> str:
    date = ewn.getDateTimeSent()
    sender = "{} ({})".format(ewn.getFromUser(), ewn.getFromOrg())

    return date + "\n" + sender