import datetime

import pandas

import OAuth.config as config

from OAuth.MailClasses import AconexMail, getRFIMailTypes, getAllMail, searchForMail

mailData = {
    "Status": [],
    "Ball in Court": [],
    "Reference Number": [],
    "Subject": [],
    "Originally From": [],
    "RFI Description": [],
    "Discipline(s)": [],
    "Date RFI Sent": [],
    "RFI Response": [],
    "Date RFI Responded": [],
    "Latest Correspondence": [],
    "Comments": [],
    "Date Closed": [],
    "(Helper) Hyperlink": []
}

def main():

    filename : str = "RFIs/" + config.project().projectCodePrefix()+"RFI Tracker.xlsx" #for this project, this is where the RFI data is read / written
    #importExcel(filename) #TODO - pull these
    allRowsDicts : [dict] = getAllMail(getRFIMailTypes(config.mailtypes()))

    #convert into one dictionary
    for d in allRowsDicts:
        for k, v in d.items():
            mailData[k].append(v)

    print([len(l) for l in mailData.values()])
    exportToExcel(filename, mailData)

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

        am = searchForMail(refno)
        am.setComment(comments)
        aconexMails.append(am)

    [am.debug() for am in aconexMails]
    return aconexMails

def exportToExcel(filename, mailData):
    #create sheet to write the project information
    projectinfo = {
        "Project Name": [config.project().projectName()],
        "Date Generated": [datetime.datetime.today().strftime('%d/%m/%Y')]
    }
    dataframe = pandas.DataFrame(data=projectinfo)
    with pandas.ExcelWriter(filename, mode='a', if_sheet_exists='replace') as writer:
        dataframe.to_excel(writer,
                           sheet_name="ProjectInfo",
                           header= True,
                           startrow = 0,
                           index=False) #no index col

    dataframe = pandas.DataFrame(data=mailData)  # convert into pandas data frame for exporting
    with pandas.ExcelWriter(filename,mode='a', if_sheet_exists='replace') as writer: #just paste over everything, it's easier
        dataframe.to_excel(writer,
                           sheet_name="RawData",
                           header= True,
                           startrow = 0,
                           index=False) #no index col
    print("     Mail data added to " + filename)


