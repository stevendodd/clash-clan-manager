from datetime import datetime
import os.path
import os
import json
import clashApi
import persistanceManager


class ClanManager:

    notesKey = ""
    warLeagueEndDay = 10
    rankHistory = 10
    
    storage = None
    api = None
    clanDetails = {}
    
    configFile = "data/config.json"
    dataFile = "data/mydata.json"
    backupFile = "data/backup/mydata_BK.json"
    notesDataFile = "data/notes.json"
    
    homeHeader = "data/content.html"
    homeTemplate = "templates/home.html"
    cwlTemplate = "templates/cwl.html"
    notesTemplate = "notes.html"
    warningTemplate = "warning.html"
    

    
    def __init__(self, logger):
        self._logger = logger
        
        if os.path.exists(self.configFile):
            f = open(self.configFile)
            c = json.load(f)
            email = c["email"]
            password = c["password"]
            key_name = c["keyName"]
            self.clanDetails["tag"] = c["clanTag"]
            self.notesKey = c["key"]
            
            if "history" in c:
                self.rankHistory = c["history"]
                
            self.api = clashApi.ClashApi(self, c["email"], c["password"], c["keyName"], c["clanTag"], self._logger)
            self.storage = persistanceManager.PersistanceManager(self, self._logger)
        
        
        self.clanDetails["name"] = self.api.getClanName()
        self.clanDetails["rankHistory"] = self.rankHistory
        
    def addLeagueRound(self,tag):
        lr = self.api.getLeagueRound(tag)
        if lr:
            self.storage.addLeagueRound(tag,lr)
            