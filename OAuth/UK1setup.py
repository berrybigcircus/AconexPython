import requests #for making http requests
from OAuth.APIcommon import basic_auth
import requests_cache #this will cache the API calls
requests_cache.install_cache()

LOBBYURL = 'https://constructionandengineering.oraclecloud.com/auth/token' #endpoint

clientID = 'SCP_Henry_Brothers_Python_ACONEX_client_APPID'
clientSecret = 'idcscs-843c6e85-95fe-4a30-a875-ca2ad24d01d5'

#Request a token
token = basic_auth(clientID, clientSecret)

headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
           'Authorization': token}

body = {'grant_type':'client_credentials',
        'user_id':'269118732',
        'user_site':'https://uk1.aconex.co.uk'}

response = requests.post(LOBBYURL, headers=headers, params=body)
print(str(response.status_code) + " " + response.reason)
jsonResponse = response.json()
bearer = 'Bearer ' + jsonResponse['access_token'] #Use the Access Token to make authorized requests to Aconex APIs on behalf of the authenticated user 

