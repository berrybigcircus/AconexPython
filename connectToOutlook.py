from datetime import datetime

from Setup.Outlook import find_folder, connect, getLastRan, checkEmail, autorunWFComments
from Setup.config import config

def main():
    outlook = connect()
    DEBUG = False #TODO - FOR EA OR UK1

    aconexfolder = find_folder("Aconex", outlook)

    aconexmessages = aconexfolder.items
    aconexmessages.Sort("[ReceivedTime]", True) #ensure sorted by date received

    lastRan: str = getLastRan()
    latestmessages = aconexmessages.Restrict("[ReceivedTime] >= '" + lastRan + "'")
    latestmessages = latestmessages.Restrict("Not([Categories] = 'Python Parsed')")
    config.debug(f"{latestmessages.Count=}")
    latestmessages.Sort("[ReceivedTime]", False) #start with the oldest

    runset : set[tuple] = set()
    success: bool = True

    temps = autoRunWF(DEBUG, runset)
    for tempreturn in temps:
        runset.add(tempreturn[0])
        success = success and tempreturn[1]

    for item in latestmessages:
        temp = checkEmail(DEBUG, item, runset)
        runset.add(temp[0])
        success = success and temp[1]

    if success:
        lastRan = datetime.now()
        with open(config.getOutlookLastRanLocation(), "w") as file:
            file.write(lastRan.strftime('%d/%m/%Y %H:%M %p'))
            file.close()

def autoRunWF(debug, runset):
    successreturns : list = []
    projects = ["Northampton JAWS", "Wolverhampton Police"]

    for projectname in projects:
        success = autorunWFComments(debug, projectname)

        successreturns.append([(projectname, "WTRAN"), success])

    return successreturns

main()

