import json
import datetime
import pathlib
import pickle
from base64 import b64encode

import pandas
import requests_cache
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

session = requests_cache.CachedSession('test', expire_after=600, use_temp=True)

#For setting up
def basic_auth(username, password):
    token = b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'

def jprint(obj):
    # create a formatted string of the Python JSON object
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)

#API Requests
def getAPIResponse(url, headers, explanation) -> str:
    response = session.get(url, headers=headers)

    #validate get request
    if response.status_code != 200:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))
        return None
    return response.text

def getAPIFile(url, headers, explanation):
    response = session.get(url, headers=headers)
    # validate get request
    if response.status_code != 200:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))
        return None
    return response

def putAPIResponse(url, headers, body=None, explanation=""):
    if body is None:
        response = session.put(url, headers=headers)
    else:
        response = session.put(url, headers=headers, json=body)

    # validate request
    if response.status_code != 200:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))
    else:
        print(response.status_code)
    print(response.text)

def postAPIResponse(url, headers, body=None, explanation="") -> str:
    if body is None:
        response = session.post(url, headers=headers)
    else:
        response = session.post(url, headers=headers, json=body)

    # validate request
    if response.status_code != 200 and response.status_code != 201:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))
    else:
        print(response.status_code)

    return response.text

def postAPIFile(url, headers, files, explanation) -> str:
    response = session.post(url, headers=headers, files=files)

    # validate request
    if response.status_code != 200:
        print("There was an error %s. %d %s" % (explanation, response.status_code, response.reason))

    return response.text

#Specific functions
def convertDateTimeStr(dateResponseRaw : str, format : str) -> str:
    if dateResponseRaw:
        date = datetime.datetime.strptime(dateResponseRaw, "%Y-%m-%dT%H:%M:%S.%fZ")
        return datetime.datetime.strftime(date, format)

    else:
        return ""

#convert to standard  RFC3339 format
def convertToDateTime(dateResponseRaw : str) -> datetime.datetime:
    if dateResponseRaw:
        return datetime.datetime.strptime(dateResponseRaw, "%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        return None

def indexInput(maxVal, allowedVals : list[str] = None) -> int | str | None:
    valid = False

    while valid == False:
        userInput = input("Enter index, or 'X' if none: ")

        if allowedVals: #separate list of possible input valves
            if userInput in allowedVals:
                return userInput

        if userInput.upper() == "X":
            return None

        if not userInput.isdigit():
            print("Enter a number.")
            continue

        chosenIndex = int(userInput)
        if chosenIndex > maxVal or chosenIndex < 0:
            print("Enter a number between 0 and %d." % maxVal)
            continue

        return chosenIndex

def putNoteInFirstQuestion(checklistJson, duplicateID=""): #put the id as a note in the first question of the inspection
    uniqueID: str = checklistJson["id"]
    firstItem : dict = {}
    isGroup: bool = False #whether in a group or not

    if len(checklistJson["items"]):
        firstItem = next(filter(lambda x: x["item_number"] == "1", checklistJson["items"]), None)
        isGroup = False
    if not firstItem:
        firstItem = [x for itemJson in checklistJson["groups"] for x in itemJson["items"] if x["item_number"] == "1"][0]
        isGroup = True

    assert firstItem

    # if not firstItem["response"]:
    #     return [], [] #add no comment if first box is empty

    currentComment = firstItem["note"]["comment"] + "\n" if firstItem["note"] else ""
    id = firstItem["id"]
    firstItem.clear()
    firstItem["id"] = id

    firstItem["comment"] = currentComment + "Unique ID: " + uniqueID #add ID to the note text
    if duplicateID != "": #if this checklist is a duplicate, add this into the comment as well
        firstItem["comment"] = firstItem["comment"] + "\nDuplicate of " + duplicateID

    if isGroup:
        groupJson = [{"id": checklistJson["groups"][0]["id"],
                     "items": firstItem}]

        return [], groupJson
    else:
        return firstItem, []

ORGFILTERENDS = ["Ltd", "Limited", "LLC", "LLP", "Inc", "Pty", "Pte", "Pvt", "Consulting", "(midlands)"]  # remove these from the organisation name when creating/searching for company mailing group
ORGFILTERSTARTS = ["The"]

def cleanOrgName(orgName : str) -> str:
    if not orgName:
        return ""

    orgWords = orgName.split(" ")  # split into words
    orgWords = orgWords if orgWords[0] not in ORGFILTERSTARTS else orgWords[1:]
    while orgWords[-1] in ORGFILTERENDS:
        orgWords = orgWords[:-1]
    return " ".join(orgWords)


def importLastRun(filename : str) -> datetime.datetime | None:
    print("Importing date from tracker at %s" % filename)
    #Get the date the tracker was last imported
    try:
        excelDataDF = pandas.read_excel(open(filename, 'rb'), sheet_name="ProjectInfo")

    except FileNotFoundError:
        print("File not found.")
        return None

    try:
        if type(excelDataDF.loc[0]["Date Generated"]) == str:
            return datetime.datetime.strptime(excelDataDF.loc[0]["Date Generated"], "%d/%m/%Y %H:%M")

        elif type(excelDataDF.loc[0]["Date Generated"]) == pandas.Timestamp():
            return excelDataDF.loc[0]["Date Generated"].to_pydatetime()

        else:
            raise Exception

    except:
        print("Could not parse ExportedData to get the Date last generated. Check the formatting of the file.")
        return None

def SelLogIn(config):
    driver = webdriver.Edge()
    driver.get("{env}/hub/index.html".format(env=config.env()))
    wait = WebDriverWait(driver, 60)
    # type email into first screen
    wait.until(EC.element_to_be_clickable((By.ID, "userName"))).send_keys("nicole.millinship@henrybrothers.co.uk")
    nextbutton = driver.find_element(By.ID, "nextButton")
    nextbutton.click()

    if config.env() == "https://uk1.aconex.co.uk":
        # Microsoft account selection
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
                                                   "div[aria-label='Sign in with nicole.millinship@henrybrothers.co.uk work or school account.']"))).click()
        # pick aconex account
        wait.until(EC.element_to_be_clickable((By.ID, config.project.getMyUserID()))).click()

    else:
        #Click 'I Agree'
        wait.until(EC.element_to_be_clickable((By.ID, '_oj1|text'))).click()

        #enter password
        wait.until(EC.element_to_be_clickable((By.ID, "ui-id-1"))).send_keys(config.getPass())

        #click sign in
        oj_btn = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "oj-button[data-testid='username-password-form-submit-btn']"))
        )
        inner_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "oj-button[data-testid='username-password-form-submit-btn'] button.oj-button-button"))
        )
        inner_btn.click()

    driver.get("{env}/hub/index.html".format(env=config.env()))
    cookies = driver.get_cookies()
    writeCookies(config, cookies)

    driver.quit()
    cj = {}
    for c in cookies:
        cj[c['name']] = c['value']

    return cookies, cj


def loadCookies(config):
    try:
        FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
        file = open(FOLDERPATH + "\\logincookies.pkl",
                    "rb")
        cookies = pickle.load(file) #dict(line.split(': ', 1) for line in file.read().splitlines())
        file.close()

        config.logger.info("Loaded cookies from logincookies.pkl")

        cj = {}
        for c in cookies:
            cj[c['name']] = c['value']
        return cookies, cj
    except FileNotFoundError:
        config.logger.error("Cookies not found. Please check the login cookies file.")
        return None, None


def writeCookies(config, cookies):
    FOLDERPATH = str(pathlib.Path(__file__).parent.resolve())
    file = open(FOLDERPATH + "\\logincookies.pkl",
                "wb")
    pickle.dump(cookies, file)
    file.close()
    config.logger.info("Cookies written to logincookies.pkl")
