import os
from dotenv import load_dotenv

import requests #for making http requests
from Setup.APIcommon import basic_auth

LOBBYURL = 'https://constructionandengineering-ea.oraclecloud.com/auth/token' #endpoint
env = "https://ea1.aconex.com"

load_dotenv()

clientID = os.getenv("EA_CLIENT_ID")
clientSecret = os.getenv("EA_CLIENT_SECRET")

#Request a token
token = basic_auth(clientID, clientSecret)

headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
           'Authorization': token}

body = {'grant_type':'client_credentials',
        'user_id':'1879050797',
        'user_site':env}

response = requests.post(LOBBYURL, headers=headers, params=body)
print(str(response.status_code) + " " + response.reason)
jsonResponse = response.json()
if jsonResponse:
    bearer = 'Bearer ' + jsonResponse['access_token'] #Use the Access Token to make authorized requests to Aconex APIs on behalf of the authenticated user

else:
    raise ConnectionError("Authentication failed")

password = os.getenv("PASSWORD")