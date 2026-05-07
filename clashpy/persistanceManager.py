import copy
import os.path
import os
import re
import json
import shutil
import tempfile
from threading import Lock


class PersistanceManager:
    
    _apiBasePath = "data/api"
    _warDataPath = _apiBasePath + "/war"
    _cwlBasePath = "data/api/cwl/"
    _membersBasePath = "data/members/"
    _membersDataFile = _membersBasePath + "members.json"
    _membersArchive =  _membersBasePath + "membersArchive.json"
    _cwlSeasonPath = None
    _manifestFile = _apiBasePath + "/manifest.json"
    
    _memberUpdateFields = [
        "tag","name","role","townHallLevel","townhallImage", "leagueTier",
        "warPreference","dateLastIn","dateLastSeen","warnings",
        "cwlWarning","warningCount","cwlWarningPenality","attackWarnings",
        "donationsReceived","donations","donationHistory",
        "donationMod","cwlRankMod","wars","averageStars",
        "averageDestruction","rank","lastThreeRank","lastThree","sort"
       ]

    _persistentMemberFields = [
        "tag", "name", "role", "townHallLevel", "warPreference",
        "dateLastIn", "dateLastSeen", "donations", "donationsReceived",
        "donationHistory", "warnings", "cwlWarning"
    ]

    _schemaVersion = 2
    _maxCwlSeasons = 6
    
    def __init__(self, clanManager, logger):
        self._clanManager = clanManager
        self._logger = logger
        self._lock = Lock()
        self._wars = []
        self._members = []
        self._currentMemberList = []
        self._warLog = {}
        
        if not os.path.exists(self._cwlBasePath):
            os.makedirs(self._cwlBasePath + "tmp", exist_ok=True)
            
        if not os.path.exists(self._warDataPath):
            os.makedirs(self._warDataPath, exist_ok=True)
            
        if not os.path.exists(self._membersBasePath):
            os.makedirs(self._membersBasePath, exist_ok=True)
            
        self._migrate()
        self._loadWars()
        self._loadMembers()


    def writeJson(self, file, data):
        dir_name = os.path.dirname(file)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name or '.')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, file)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


    def getMember(self, tag):
        with self._lock:
            for m in self._members:
                if tag == m["tag"]:
                    return copy.deepcopy(m)
        return({"tag": tag})

    def getMembers(self):
        with self._lock:
            return copy.deepcopy(self._members)

    def add_warning(self, player_tag, wdate):
        with self._lock:
            for p in self._members:
                if p["tag"] == player_tag:
                    if "warnings" in p:
                        p["warnings"].append(wdate)
                    else:
                        p["warnings"] = [wdate]
                    break

    def remove_warning(self, player_tag, date):
        with self._lock:
            for p in self._members:
                if p["tag"] == player_tag:
                    if "warnings" in p:
                        for i, w in enumerate(p["warnings"]):
                            if w == date:
                                p["warnings"].pop(i)
                                break
                    break

    def add_cwl_warning(self, player_tag, wdate):
        with self._lock:
            for p in self._members:
                if p["tag"] == player_tag:
                    if "cwlWarning" in p:
                        p["cwlWarning"].append(wdate)
                    else:
                        p["cwlWarning"] = [wdate]
                    break

    def remove_cwl_warning(self, player_tag, date):
        with self._lock:
            for p in self._members:
                if p["tag"] == player_tag:
                    if "cwlWarning" in p:
                        for i, w in enumerate(p["cwlWarning"]):
                            if w == date:
                                p["cwlWarning"].pop(i)
                                break
                    break


    def _loadMembers(self):
        if os.path.exists(self._membersDataFile):
            try:
                with open(self._membersDataFile) as f:
                    self._members = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self._logger.error("Failed to load members: %s", e)
                self._members = []

    def _persistMembers(self):
        persistent = []
        for m in self._members:
            persist = {k: m[k] for k in self._persistentMemberFields if k in m}
            persistent.append(persist)
        self.writeJson(self._membersDataFile, persistent)

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
                    self._logger.debug(status + memberUpdate["name"] + ": " + str(memberUpdate))

        self._persistMembers()
  
    def archiveMember(self, member):
        with self._lock:
            target = None
            for m in self._members:
                if m["tag"] == member["tag"]:
                    target = m
                    self._members.remove(m)
                    break

        if target is not None:
            persistent = {k: target[k] for k in self._persistentMemberFields if k in target}
            existing = []
            if os.path.exists(self._membersArchive):
                try:
                    with open(self._membersArchive) as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, IOError):
                    existing = []
            existing.append(persistent)
            self.writeJson(self._membersArchive, existing)
    
            
    def addCwlSeason(self, season, league):
        self._cwlSeasonPath = self._cwlBasePath + season
        os.makedirs(self._cwlSeasonPath, exist_ok=True)
        self.writeJson(self._cwlSeasonPath + "/league.json", league)
        self._pruneCwlSeasons()
    
        
    def addLeagueRound(self, tag, leagueRound):
        self.writeJson(self._cwlSeasonPath + "/" + tag + ".json", leagueRound)    
    
               
    def getLatestCWL(self):
        self._latestCWL = max([os.path.join(self._cwlBasePath,d) for d in os.listdir(self._cwlBasePath) 
                     if os.path.isdir(os.path.join(self._cwlBasePath, d))], key=os.path.getmtime)
        return(self._latestCWL)
    
    def getCwlLeague(self):
        latestCWL = self.getLatestCWL()
        
        if os.path.exists(latestCWL + "/league.json"):
            try:
                with open(latestCWL + "/league.json") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self._logger.error("Failed to load CWL league: %s", e)
                return None
        else:
            return None
        
    def getCwlRound(self,tag):
        if os.path.exists(self._latestCWL + "/" + tag + ".json"):
            try:
                with open(self._latestCWL + "/" + tag + ".json") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self._logger.error("Failed to load CWL round %s: %s", tag, e)
                return None
        else:
            return None
        
    
    def setWarLog(self,warLog):
        self._warLog = warLog
        self.writeJson(self._apiBasePath + "/warLog.json", warLog)
    
    
    def getWarLog(self):
        return(self._warLog)
    
    
    def setWars(self,wars):
        self._wars = wars
        
        
    def getWars(self):
        return(self._wars)
    
    
    def _loadWars(self):
        warFiles = [os.path.join(self._warDataPath,d) for d in os.listdir(self._warDataPath)]
        warFiles = self._sortAlphaNum(warFiles)
        self._logger.debug("War files: %s", warFiles)
        for wf in reversed(warFiles):
            try:
                with open(wf) as f:
                    self._wars.append(json.load(f))
            except (json.JSONDecodeError, IOError) as e:
                self._logger.error("Failed to load war file %s: %s", wf, e)
        max_wars = self._clanManager.rankHistory + 1
        if len(self._wars) > max_wars:
            self._wars = self._wars[:max_wars]
            
            
    def addWar(self,war):
        if "preparationStartTime" in war:
            if len(self._wars)>0 and self._wars[0]["preparationStartTime"] == war["preparationStartTime"]:
                self._wars[0] = war
            else:
                self._wars.insert(0, war)
                
            warFileName = self._warDataPath + '/' + war["preparationStartTime"] + ".json"
            self.writeJson(warFileName, war)
                
        to_remove = [i for i, w in enumerate(self._wars) if w["state"] == "preparation" and i > 0]
        for i in reversed(to_remove):
            self._logger.debug('delete: ' + self._wars[i]['state'])
            self._wars.pop(i)

        for i, w in enumerate(self._wars):
            if i > 0 and w["state"] == "inWar":
                self._wars[i]["state"] = "warEnded"
                self._logger.debug('fix: ' + self._wars[i]['state'] + " " + self._wars[i]['endTime'])
        
        # Only keep last N wars
        if len(self._wars) > 0:
            if self._wars[0]['state'] != "warEnded":       
                self._wars = self._trimList(self._wars,self._clanManager.rankHistory+1)
            else:
                self._wars = self._trimList(self._wars,self._clanManager.rankHistory)
                
        return(self._wars) 
    
    
    def _trimList(self, items, size):
        return items[:size]
    
    def _sortAlphaNum(self, items):
        convert = lambda text: int(text) if text.isdigit() else text
        alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
        return sorted(items, key=alphanum_key)

    def _pruneCwlSeasons(self):
        if not os.path.exists(self._cwlBasePath):
            return
        seasons = sorted([
            os.path.join(self._cwlBasePath, d)
            for d in os.listdir(self._cwlBasePath)
            if os.path.isdir(os.path.join(self._cwlBasePath, d)) and not d.endswith('tmp')
        ])
        if len(seasons) > self._maxCwlSeasons:
            for season_dir in seasons[:-self._maxCwlSeasons]:
                self._logger.info("Pruning old CWL season: %s", season_dir)
                shutil.rmtree(season_dir)

    def _migrate(self):
        if os.path.exists(self._manifestFile):
            try:
                with open(self._manifestFile) as f:
                    manifest = json.load(f)
                    if manifest.get("schema_version", 0) >= self._schemaVersion:
                        return
            except (json.JSONDecodeError, IOError):
                pass

        if os.path.exists(self._membersDataFile):
            try:
                with open(self._membersDataFile) as f:
                    members = json.load(f)
                stripped = []
                for m in members:
                    persist = {k: m[k] for k in self._persistentMemberFields if k in m}
                    stripped.append(persist)
                self.writeJson(self._membersDataFile, stripped)
                self._logger.info("Migrated members.json to schema version %d", self._schemaVersion)
            except (json.JSONDecodeError, IOError) as e:
                self._logger.error("Failed to migrate members.json: %s", e)

        self.writeJson(self._manifestFile, {"schema_version": self._schemaVersion})