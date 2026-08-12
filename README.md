# Setup

Requires `setup.py` file within the [Setup folder](https://github.com/berrybigcircus/AconexPython/tree/master/Setup) that stores the OAuth API key and secret. The bearer produced is used for future API requests.
Sample setup.py file:
```
LOBBYURL = 'https://constructionandengineering-ea.oraclecloud.com/auth/token'  #TODO - URL for Early Access environment
clientID = "abc" #TODO
clientSecret  = "1234" #TODO

USERID = "1234" #TODO - Aconex ID for account with API access
USERSITE = "https://ea1.aconex.com" #TODO - Early Access webpage URL

#Request a token
token = basic_auth(clientID, clientSecret)

headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
           'Authorization': token}

body = {'grant_type':'client_credentials',
        'user_id': USERID,
        'user_site': USERSITE}

response = requests.post(LOBBYURL, headers=headers, params=body)
print(str(response.status_code) + " " + response.reason)
jsonResponse = response.json()
#Use the Access Token to make authorized requests to Aconex APIs on behalf of the authenticated user
bearer = 'Bearer ' + jsonResponse['access_token'] 
```
A unique setup file must be created for each environment (EA1, UK1, etc.).

## Initialising
`config.py` stores the bearer and environment variables, as well as a debug logger, and the selected project. `init` must be called before running any of the programs. The `debug` parameter can be used to explicitly specify the project, rather than ask the user. 

```
from Setup import setup
from Setup.config import init, config

# Initialise with no project selected
init(setup.bearer, setup.env, debug=None)  
# Initialise with a pre-chosen project
init(setup.bearer, setup.env, debug=["HB Test", #Project Name
                                  "1879048648", #Project ID
                                  "HBT"]) #Project Code

```
Once init has been ran, the global variable config is set and can be used to get the project (if selected), the environment, and the logger.
```
assert config.projectname() == "HB Test"
config.info("'HB Test' initialised")
config.debug(config.projecturl()) #This is the url needed for most API requests
```
All logs are outputted to the command line and to `debug.log` within the Logs folder.

## Get All Projects
Most programs require the list of projects the account has access to beforehand in order to run. Run `getAllProjects.py` to convert this into a csv list. 
```
from Setup import setup

init(setup.bearer, setup.env, debug=None)
getAllProjects.main()
```

This will generate a projectslist.csv file within the [getAllProjects folder](https://github.com/berrybigcircus/AconexPython/tree/master/Setup/getAllProjects) that will be used by `Project.py`.

### Project Selection
Once the csv has been created, the user can be prompted to select a project from the list
```
from Setup import setup
init(setup.bearer, setup.env, debug=[]) #User selects project
```
```
#Example Project selection output:
CURRENT PROJECTS:
0 - ABC Project 1 (1234)
1 - DEF Project 2 (5678)
```
Selection can be inputted by entering either the project code, or the index.

# A) Project Directory & Invitation
[Directory](https://github.com/berrybigcircus/AconexPython/tree/master/a_NewUser) has two functions:
```
from a_Directory import Directory
#Create an excel project directory from the Aconex project directory for a selected project
Directory.createProjectDirectory()

#Perform project invitation process for a selection of inputted names/emails for a selected project
Directory.main()
```
## Create Project Directory
The in-built online project directory within Aconex has some limitations that mean it can't be fully relied on as the ultimate directory of a construction project:
* The Aconex directory does not list out email addresses of users, unless they are an organisation admin, or a guest.
* The directory information is only as useful as the information inputted by the user/organisation, i.e. incorrect job titles, addresses, and missing mobile numbers can't be rectified by anyone other than the source user

This program tries to combine the breadth of the Aconex project directory (which includes all designers, subcontractors and client team members) with the more accurate information of Outlook by pulling the missing data from my Outlook contacts for each Aconex user and exporting to an excel file. Within my Outlook contacts, a list of people, with their companies, emails, mobiles, and Aconex User ID is stored, if known.<br>

Rather than iterate through each user, using the `show_groups` parameter of directory search request, it iterates through each mailing group. This removes cases where the same organisation is registered under different variants.<br>
Another API call then lists the users within that mailing group and gets their details. Using these details, the Outlook contacts folder is filtered using a set of DASL queries to see if the user exists.
```
#Different DASL queries to perform to try to match to outlook contacts
sfilters = ["@SQL=""urn:schemas:contacts:governmentid"" = \'{aid}\'".format(aid = aconexid),
            "[FullName] = {f}".format(f=fullname),
            "@SQL=""urn:schemas:contacts:o"" = \'{c}\' AND ""urn:schemas:contacts:fileas"" LIKE \'%{l}\'".format(c=company,
                                                                                                   l=lastname) 
            ]
```
The first filter is the most reliable match as it uses the unique Aconex ID, which is stored in my contacts under the in-built 'governmentid' Outlook field. If not found, a full name search is performed. In case of first name variants (e.g. Phil/Philip, Dan/Daniel, etc.), the third filter uses the company name and surname.
The found outlook contact is passed into an OutlookContact object which wraps the contact details fields. It calls a special function to parse Exchange email addresses useing the MAPI ID to resolve the email into a recipient, convert to an exchange user, and get the SMTP address.
The object details are used to populate a dictionary which will eventually be converted to a pandas dataframe and written to excel.

### Known Limitations
* Reliant on active connection to Outlook application to run
* Requires all relevant users to be on Aconex and to have a mailing group detailing their role
* Reliant on quality of Outlook Contacts and external storage of email addresses / mobiles. Can potentially mismatch if two people have identical first/last names.

## Project Invitation
On invitation to an Aconex project, the following occurs:
1. User is added to project
2. User is added to relevant mailing groups (typically the 'All' mailing group and a company mailing group)
3. Documents are transmitted to user
4. 'Project invite' mail template is sent to user to introduce them to Aconex

The API cannot invite users to a project directly, but it can check if the user has an account in the global directory, and it can do steps 2-4. Names are added to `user_list.txt`:
```
##Enter user emails / full names below, on separate lines:
Anthony Apple <abc@mail.com>
Max Rebo <maxrebo@cantina.com>
```
If email addresses are included, the code will parse the email and use it as the parameter to search with when calling searchProjectDirectory. This can be more reliable than the name, as first names can have variations.
<br>
The program performs a set of directory searches based on whether the user exists or not, detailed below. This mimics the manual process for adding users to projects.

[!Flowchart of new_user.main](z_Docs/My_Docs/directory_flowchart.png)

If the user is not found on the project, but found in the global directory, the program sends a web link to the global directory to show the found user, allowing you to add them quickly. <br>
<br>
If the user is not found in the global directory, it prompts for the company name, and runs a fuzzy search on the company name. If there is no organisation with that name, then a draft email to the user is created using win32com prompting them to register. <br>
<br> If companies are found, the user is asked to pick the matching company so that the org admins for that company can be found. The org admins are the only ones who can create an account for the new user. Unfortunately, the Aconex API does not natively expose the org admins, despite this being available on the web, so I developed two solutions:
1. Store a csv list of organisation unique IDs, trading names, org admins, and the date the org admins were last checked. This is loaded into a dictionary when the program runs. This allows a database of known org admins for common companies to be built up and checked, avoiding any web request.
2. If the company is not in the csv list, then I have had to reverse engineer the internal API request to get the org admins. This is made more complex as it relies on session cookies, so before making the GET request, I use Selenium to automate logging into Aconex, gather the cookies from the session, and use those in the request.  

Once the org admins are known, the email to them can be drafted. At the end of all scenarios, an excel tracker is updated with the user, the project, and their 'status' in the invitation process.

### Users on the Project
If/when the users in the `users_list.txt` are on the project, the program prompts each step of the invitation process.
```
##Add to All Mailing Group
confirm = input("Add all users to 'All' Mailing Group? (Y/N): ")
if confirm.upper() == "Y" or confirm.lower() == "yes": addToAll(userData)
```
When creating the company mailing group, some cleaning of the company name to remove, e.g. the words "Limited", "Ltd" is required to shorten the group name below the maximum number of characters. 
<br> Drafting of the transmittal makes use of a unique document register search function to remove internal files. It mirrors a saved search set up on all projects. The `allTransmittal.xml` xml template is used to quickly create the transmittal. Once created, the draft is opened so you can amend or send. Transmittals cannot be sent from the API, only drafted.
The 'Project Invite' mail is treated separate to the transmittal as some users do not need a transmittal when invited to the project. As each project invite's mail body is unique to the project, this is pulled from an existing draft that sits in each project's draftbox and loaded into another xml template.

### Known Limitations
* The code is currently written in a fairly inflexible way where all the users in the list must be added to the same project and then go through the same invitation process. If two users are on the list from the same company, they are not 'grouped', so if an email needs to be sent, the email could be sent twice.
* If the user is prompted to match the company, this is not easy to do with the name / ID, as organisations can be registered from multiple regions, registered as a guest, etc. It can create trial/error to find the match. 
* The workaround to get org admins is a hack solution but there doesn't currently seem to be a better method. Because it is relying on the local csv data as its first point, there is a chance the list of org admins is out of date.