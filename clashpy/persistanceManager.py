import os.path
import os
import re
import json
from threading import Lock


class PersistanceManager:
    
    _apiBasePath = "data/api"
    _warDataPath = _apiBasePath + "/war"
    _cwlBasePath = "data/api/cwl/"
    _membersBasePath = "data/members/"
    _membersDataFile = _membersBasePath + "members.json"
    _membersArchive =  _membersBasePath + "membersArchive.json"
    _cwlSeasonPath = None
    
    _wars = []
    _members = []
    _currentMemberList = []
    _memberUpdateFields = [
        "tag","name","role","townHallLevel","townhallImage",
        "warPreference","dateLastIn","dateLastSeen","warnings",
        "cwlWarning","warningCount","cwlWarningPenality","attackWarnings",
        "donationsReceived","donations","donationHistory",
        "donationMod","cwlRankMod","wars","averageStars",
        "averageDestruction","rank","lastThreeRank","lastThree","sort"
       ]
    
    def __init__(self, clanManager, logger):
        self._clanManager = clanManager
        self._logger = logger
        self._lock = Lock()
        
        self._warLog = {
            "items": [], 
            "currentState": "warEnded"
        }

        if not os.path.exists(self._cwlBasePath):
            os.makedirs(self._cwlBasePath + "tmp")
            
        if not os.path.exists(self._warDataPath):
            os.makedirs(self._warDataPath)
            
        if not os.path.exists(self._membersBasePath):
            os.makedirs(self._membersBasePath)
            
        self._loadWars()
        self._loadMembers()
 
 
    def writeJson(self,file,data):
        with open(file, 'w') as f:
            json.dump(data, f, indent=2)
                       

    def getMember(self, tag):
        for m in self._members:
            if tag == m["tag"]:
                return(m)
        return({"tag": tag})

    def getMembers(self):
        return(self._members)


    def _loadMembers(self):
        if os.path.exists(self._membersDataFile):
            self._members = json.load(open(self._membersDataFile))
            

    def updateMembers(self, members):
        with self._lock:
            found = False
            for member in members:
                memberUpdate = {}
                for i, existingMember in enumerate(self._members):
                    if existingMember["tag"] == member["tag"]:
                        memberUpdate = existingMember
                        found = True
                        break               

                for field in self._memberUpdateFields:
                    if field in member:                  
                        memberUpdate[field] = member[field]
        
                status = "Updating "
                        
                if not found:
                    status = "Adding "
                    self._members.append(memberUpdate)
                else:
                    self._members[i] = memberUpdate
                
                if "currentMemberNumber" in member:
                    status = status + "[" + str(member["currentMemberNumber"] + 1) + "|" + str(len(self._currentMemberList)) + "] "
                
                if "name" in memberUpdate:    
                    self._logger.debug(status  + memberUpdate["name"] + ": " + str(memberUpdate))
                    self.writeJson(self._membersDataFile, self._members)
  
    def archiveMember(self, member):
        for m in self._members:
            if m["tag"] == member["tag"]:
                
                with open(self._membersArchive, "a") as f:
                    json.dump(m, f, indent=2)
                
                self._members.remove(m)
                break
    
            
    def addCwlSeason(self, season, league):
        self._cwlSeasonPath = self._cwlBasePath + season
        if not os.path.exists(self._cwlSeasonPath):
            os.makedirs(self._cwlSeasonPath)
            
        self.writeJson(self._cwlSeasonPath + "/league.json", league)
    
        
    def addLeagueRound(self, tag, leagueRound):
        self.writeJson(self._cwlSeasonPath + "/" + tag + ".json", leagueRound)    
    
              
    def getLatestCWL(self):
        self._latestCWL = max([os.path.join(self._cwlBasePath,d) for d in os.listdir(self._cwlBasePath) 
                     if os.path.isdir(os.path.join(self._cwlBasePath, d))], key=os.path.getmtime)
        return(self._latestCWL)
    
    def getCwlLeague(self):
        latestCWL = self.getLatestCWL()
        
        if os.path.exists(latestCWL + "/league.json"):
            f = open(latestCWL + "/league.json")
            return(json.load(f))
        else:
            return None
        
    def getCwlRound(self,tag):
        if os.path.exists(self._latestCWL + "/" + tag + ".json"):
            f = open(self._latestCWL + "/" + tag + ".json")
            return(json.load(f))
        else:
            return None
        
    
    def setWarLog(self,warLog):
        self._warLog = warLog
        self.writeJson(self._apiBasePath + "/warLog.json", warLog)
    
    
    def getWarLog(self):
        if not hasattr(self, "_warLog"):
            self._warLog = {"items": [], "currentState": "warEnded"}
        return self._warLog
    
    
    def setWars(self,wars):
        self._wars = wars
        
        
    def getWars(self):
        return(self._wars)
    
    
    def _loadWars(self):
        warFiles = [os.path.join(self._warDataPath,d) for d in os.listdir(self._warDataPath)]
        warFiles = self._sortAlphaNum(warFiles)
        print(warFiles)
        for wf in reversed(warFiles):
            self._wars.append(json.load(open(wf)))
        
            
    def addWar(self,war):
        if "preparationStartTime" in war:
            if len(self._wars)>0 and self._wars[0]["preparationStartTime"] == war["preparationStartTime"]:
                self._wars[0] = war
            else:
                self._loadWars()                       
                self._wars.insert(0, war)
                
            warFileName = self._warDataPath + '/' + war["preparationStartTime"] + ".json"
            self.writeJson(warFileName, war)
                
        for i, w in enumerate(self._wars):
            if w["state"] == "preparation" and i>0:
                self._logger.debug('delete: ' + self._wars[i]['state'])
                self._wars.pop(i)
            else:
                if w["state"] == "inWar" and i>0:
                    w["state"] = "warEnded"
                       
                self._logger.debug('keep: ' + self._wars[i]['state'] + " " + self._wars[i]['endTime'])
        
        # Only keep last 10 wars
        if len(self._wars) > 0:
            if self._wars[0]['state'] != "warEnded":       
                self._wars = self._trimList(self._wars,self._clanManager.rankHistory+1)
            else:
                self._wars = self._trimList(self._wars,self._clanManager.rankHistory)
                
        return(self._wars) 
    
    
    def _trimList(self, list, size):
        n = len(list)
        for i in range(0, n - size ):
            list.pop()
        return(list)
    
    def _sortAlphaNum(self, list):
        convert = lambda text: int(text) if text.isdigit() else text
        alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
        return sorted(list, key = alphanum_key)