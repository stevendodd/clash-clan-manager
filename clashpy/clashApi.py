import requests
import json
from datetime import datetime
from json import loads as json_loads
from base64 import b64decode as base64_b64decode



class ClashApi:

    def __init__(self, clanManager, email, password, key_name, clanTag, logger):
        self._clanManager = clanManager
        self._email = email
        self._password = password
        self._key_name = key_name
        self._logger = logger
        self._token = self._getToken()
        self._updateMember = 0
        self._clanName = None
        
        self._apiUrls = {
            "currentwar": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar",
            "clan": "https://api.clashofclans.com/v1/clans/%23" + clanTag,
            "warlog": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/warlog?limit=20",
            
            "league": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar/leaguegroup",
            "leagueRound": "https://api.clashofclans.com/v1/clanwarleagues/wars/%23",
            "player": "https://api.clashofclans.com/v1/players/%23",
            "season": "https://api.clashofclans.com/v1/goldpass/seasons/current",
            "verifytoken": "/verifytoken"
        }
        
        response = requests.get(self._apiUrls["clan"], headers={'Authorization': 'Bearer ' + self._token})
        if response.status_code != 200:
            exit(str(response) + ": Failed to get clan")
        else:
            self._clanName = response.json()["name"]

    def _getToken(self):
        key_count = 1
        keys = _keys = []
        KEY_MAXIMUM = 10
        
        s = requests.Session() 
        body = {"email": self._email, "password": self._password}
        
        resp = s.post("https://developer.clashofclans.com/api/login", json=body)
        if resp.status_code == 403:
            raise InvalidCredentials(resp)
        
        self._logger.debug("Successfully logged into the developer site.")
        
        resp_paylaod = resp.json()
        ip = json_loads(base64_b64decode(resp_paylaod["temporaryAPIToken"].split(".")[1] + "====").decode("utf-8"))["limits"][1]["cidrs"][0].split("/")[0]
        
        self._logger.debug("Found IP address to be %s", ip)
        
        resp = s.post("https://developer.clashofclans.com/api/apikey/list")
        if "keys" in resp.json():
            keys = (resp.json())["keys"]
            _keys.extend(key["key"] for key in keys if key["name"] == self._key_name and ip in key["cidrRanges"])
        
            self._logger.debug("Retrieved %s valid keys from the developer site.", len(_keys))
        
            if len(_keys) < key_count:
                for key in (k for k in keys if k["name"] == self._key_name and ip not in k["cidrRanges"]):
                    self._logger.debug(
                        "Deleting key with the name %s and IP %s (not matching our current IP address).",
                        self._key_name, key["cidrRanges"],
                    )
                    s.post("https://developer.clashofclans.com/api/apikey/revoke", json={"id": key["id"]})
        
        while len(_keys) < key_count and len(keys) < KEY_MAXIMUM:
            data = {
                "name": self._key_name,
                "description": "Created on {}".format(datetime.now().strftime("%c")),
                "cidrRanges": [ip],
                "scopes": ["clash"],
            }
        
            self._logger.debug("Creating key with data %s.", str(data))
        
            resp = s.post("https://developer.clashofclans.com/api/apikey/create", json=data)
            key = resp.json()
            self._logger.debug(resp.json())
            _keys.append(key["key"]["key"])
        
        if len(keys) == 10 and len(_keys) < key_count:
            self._logger.debug("%s keys were requested to be used, but a maximum of %s could be "
                         "found/made on the developer site, as it has a maximum of 10 keys per account. "
                         "Please delete some keys or lower your `key_count` level."
                         "I will use %s keys for the life of this client.",
                         key_count, len(_keys), len(_keys))
        
        if len(_keys) == 0:
            raise RuntimeError(
                "There are {} API keys already created and none match a key_name of '{}'."
                "Please specify a key_name kwarg, or go to 'https://developer.clashofclans.com' to delete "
                "unused keys.".format(len(keys), self._key_name)
            )
        
        self._logger.debug("Successfully initialised keys for use.")
        return(_keys[0])


    def getClanName(self):
        return self._clanName

    def getApiData(self):
        latestCurrentWar = {}
        response = requests.get(self._apiUrls["currentwar"], headers={'Authorization': 'Bearer ' + self._token})
        
        if response.status_code == 403:
            self._logger.debug("Attempting to refresh token")
            self._token = self._getToken(self._email, self._password, self._keyName)
            response = requests.get(self._apiUrls["currentwar"], headers={'Authorization': 'Bearer ' + self._token})
            
        if response.status_code == 200 and "preparationStartTime" in response.json():
            self._clanManager.storage.addWar(response.json())
            latestCurrentWar = response.json()
        
        latestClan = {}
        response = requests.get(self._apiUrls["clan"], headers={'Authorization': 'Bearer ' + self._token})
        if response.status_code == 200 and response.json():
            latestClan = response.json()
        
            response = requests.get(latestClan["badgeUrls"]["small"])
            if response.status_code == 200:
                open('static/badge.png', 'wb').write(response.content)
        else:
             self._logger.error("Couldn't load clan data from API: " + str(response.status_code))
             return("")
            
        latestWarLeague = {}
        response = requests.get(self._apiUrls["league"], headers={'Authorization': 'Bearer ' + self._token})
        if response.status_code == 200 and response.json():
            latestWarLeague = response.json()
        
        latestWarLog = {}
        response = requests.get(self._apiUrls["warlog"], headers={'Authorization': 'Bearer ' + self._token})
        if response.status_code == 200 and response.json():
            latestWarLog = response.json()
        
        latestPlayers = []
        for r in range(5):
            if self._updateMember >= len(latestClan["memberList"]):
                    self._updateMember = 0
                    
            playerTag = latestClan["memberList"][self._updateMember]["tag"].strip("#")
            response = requests.get(self._apiUrls["player"] + playerTag, headers={'Authorization': 'Bearer ' + self._token})
            if response.status_code == 200 and response.json():
                latestPlayers.append(response.json())
                self._updateMember += 1
                
        return({"updateMember": self._updateMember, 
                "currentWar": latestCurrentWar,
                "warLeague": latestWarLeague,
                "clan": latestClan,
                "warLog": latestWarLog,
                "players": latestPlayers})  
        
    def getLeagueRound(self,tag):
        response = requests.get(self._apiUrls["leagueRound"] + tag, headers={'Authorization': 'Bearer ' + self._token})
        if response.status_code == 200 and response.json():
            return response.json()
        else:
            return None
        
    def verifytoken(self,tag):
        response = requests.get(self._apiUrls["player"] + tag + self._apiUrls["verifytoken"], headers={'Authorization': 'Bearer ' + self._token})
        if response.status_code == 200 and response.json():
            return response.json()["status"]
        else:
            return None
        
        
    def getClan(self):
        response = requests.get(self._apiUrls["clan"], headers={'Authorization': 'Bearer ' + self._token})
        if response.status_code == 200 and response.json():
            return response.json()

        else:
             self._logger.error("Couldn't load clan data from API: " + str(response.status_code))
             return None