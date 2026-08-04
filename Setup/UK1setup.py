import os
from dotenv import load_dotenv

import requests #for making http requests
from Setup.APIcommon import basic_auth

LOBBYURL = 'https://constructionandengineering.oraclecloud.com/auth/token' #endpoint
env = "https://uk1.aconex.co.uk"

load_dotenv()

clientID = os.getenv('UK_CLIENT_ID')
clientSecret = os.getenv('UK_CLIENT_SECRET')

#Request a token
token = basic_auth(clientID, clientSecret)

headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
           'Authorization': token}

body = {'grant_type':'client_credentials',
        'user_id':'269118732',
        'user_site':env}

response = requests.post(LOBBYURL, headers=headers, params=body)
print(str(response.status_code) + " " + response.reason)
if response.status_code != 200:
    raise ConnectionError("Authentication failed")

jsonResponse = response.json()
bearer = 'Bearer ' + jsonResponse['access_token'] #Use the Access Token to make authorized requests to Aconex APIs on behalf of the authenticated user
