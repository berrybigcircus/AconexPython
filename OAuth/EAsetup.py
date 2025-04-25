import requests #for making http requests
from OAuth.APIcommon import basic_auth
import requests_cache #this will cache the API calls
requests_cache.install_cache()

LOBBYURL = 'https://constructionandengineering-ea.oraclecloud.com/auth/token' #endpoint
env = "https://ea1.aconex.com"

clientID = 'SCP_Henry_Brothers_Aconex_Aconex_client_APPID'
clientSecret = '4342a5ca-d9d1-492c-a135-61736eaf8395'

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
bearer = 'Bearer ' + jsonResponse['access_token'] #Use the Access Token to make authorized requests to Aconex APIs on behalf of the authenticated user
