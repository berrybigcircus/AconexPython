from Setup import UK1setup, EAsetup, Mail
from Setup.config import init, config
from Setup.getAllProjects import getAllProjects
from a_NewUser import newUser
from b_Workflow import WorkflowComments
from c_Field import exporting, IssuesPhotos, inspectionPDF
from d_Mail.Import import ImportFromExcel, OutlookChecker
from d_Mail.RFIs import RFITracker
from d_Mail.NEC_EWN import NEC_EWN
from e_DocUpdating import RelatedItems

import time

def getProjects():
    init(UK1setup.bearer, UK1setup.env, debug=None)  # No project
    getAllProjects.main()

def newUserMain(createdirectory : bool = False):

    if createdirectory:
        newUser.createProjectDirectory()
    else:
        newUser.main()


def WFCommsMain():
    WorkflowComments.main(inputUseTextFile="n", forceAll=True)
    #WorkflowComments.main(inputUseTextFile=input("Generate from docsList.txt? (Y/N): ").lower())

    #TODO - make WF tracker upload itself to doc register

def fieldMain():
    #Export data (WIP)
    #exporting.main(EAsetup.bearer, "https://ea1.aconex.com")  # pass in environment, for urls

    #Inspection PDF Creator
    #inspectionPDF.main(EAsetup.bearer, "https://ea1.aconex.com")

    #Issues Photos
    #IssuesPhotos.downloadFieldPhotos()
    IssuesPhotos.uploadFieldPhotos()

def docMain():
    RelatedItems.main()

def MailMain():
    #RFITracker.test()
    #RFITracker.main()
    #RFITracker.sendDraft(config, "https://ea1.aconex.com/hub/index.html?mainTarget=%2Frsrc%2F20250422.1347%2Fen_AU_DOC%2Fmail%2Fview%2Findex.html%23%2F1879048648%2F1880257357")
    #RFITracker.uploadRFITracker(r"C:\Users\nicole.millinship\PycharmProjects\AconexPython\d_Mail\RFIs\Trackers\MTP - RFI Tracker.xlsx")
    #NEC_EWN.main()
    #ImportFromExcel.main(False)
    OutlookChecker.main()

#load all MOJ RFI trackers
def mojRFIs():
    # init(UK1setup.bearer, UK1setup.env, debug=["HMCTS Manchester", "268459030", "51023"])
    # RFITracker.main()

    init(UK1setup.bearer, UK1setup.env, debug=["HMCTS Nottingham", "268458266", "9910"])
    RFITracker.main()

    # init(UK1setup.bearer, UK1setup.env, debug=["HMCTS Telford", "268459032", "9661"])
    # RFITracker.main()
    #
    # init(UK1setup.bearer, UK1setup.env, debug=["HMCTS Lincoln", "268459033", "9907"])
    # RFITracker.main()
#run
def main():
    #getProjects()

    #INIT
    #init(EAsetup.bearer, EAsetup.env, debug=["HB Test", "1879048648", "HBT"]) #HB Test project
    # config.setPass(EAsetup.password)
    #init(UK1setup.bearer, UK1setup.env, debug=["DfE Wisbech Free School", "268454433", "FS1018"]) #Wisbech
    #init(UK1setup.bearer, UK1setup.env, debug=["Stechford Police","268456391", "SPR"]) #Stechford
    #init(UK1setup.bearer, UK1setup.env, debug=["QMC Endoscopy", "268456597", "QMC"]) #QMC Nendo
    #init(UK1setup.bearer, UK1setup.env, debug=["NUHT Community Diagnostics Centre", "268456728", "CDC"]) #CDC
    #init(UK1setup.bearer, UK1setup.env, debug=["MTP", "268457782", "MTP"])
    #init(UK1setup.bearer, UK1setup.env, debug=[]) #Select project

    #RUN PACKAGES
    #newUserMain(createdirectory=False)
    #WFCommsMain()
    #fieldMain()
    # docMain()
    MailMain()
    #mojRFIs()

    config.logger.info("Ran in %.2f seconds" % (time.time() - start_time))

start_time = time.time()
main()