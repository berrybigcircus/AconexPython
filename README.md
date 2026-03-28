# Setup

Requires setup.py file within Setup that stores the OAuth API key and secret. The bearer produced is used for future API requests.
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

## Get All Projects

Most programs require the list of projects the account has access beforehand in order to run.
