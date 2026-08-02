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
Any 
```
from Setup import setup
from Setup.config import init, config

# Initialise with no project selected
init(setup.bearer, setup.env, debug=None)  
# Initialise with a pre-chosen project, using its project ID
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
All logs are outputted to the command line and to [].

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
[]
Selection can be inputted by entering either the project code, or the index.

# A) Project Directory & Invitation
[NewUser](https://github.com/berrybigcircus/AconexPython/tree/master/a_NewUser) has two functions:
```
from a_NewUser import newUser
#Create an excel project directory from the Aconex project directory for a selected project
newUser.createProjectDirectory()

#Perform project invitation process for a selection of inputted names/emails for a selected project
newUser.main()
```
## Create Project Directory
