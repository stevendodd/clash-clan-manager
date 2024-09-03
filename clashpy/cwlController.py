from datetime import datetime


class CwlController:
    
    currentRound = None
    remainingTime = None
    rounds = None
    results = None
    
    def __init__(self, clanManager, logger):
        self._logger = logger
        self._clanManager = clanManager
        
        
    def process(self,latestApiData):
        if "season" in latestApiData["warLeague"]:
            self._logger.debug(latestApiData["warLeague"]["season"])
            self._clanManager.storage.addCwlSeason(latestApiData["warLeague"]["season"],latestApiData["warLeague"])
         
            for r in latestApiData["warLeague"]["rounds"]:
                for tag in r["warTags"]:
                    if tag != "#0":
                        self._clanManager.addLeagueRound(tag.strip("#"))
                        
        
        #latestCWL = self._clanManager.storage.getLatestCWL()
        latestApiData["warLeague"] = self._clanManager.storage.getCwlLeague()
        
        if latestApiData["warLeague"]:
            self._logger.debug("Processing " + latestApiData["warLeague"]["season"] + " Season")      
            self.results = {}
            self.results["clans"] = []
            self.results["players"] = []
            for leagueClan in latestApiData["warLeague"]["clans"]:
                self.results["clans"].append({"tag": leagueClan["tag"], 
                                         "name": leagueClan["name"],
                                         "badgeUrls": leagueClan["badgeUrls"], 
                                         "stars": 0, 
                                         "attacks": 0, 
                                         "destruction": 0,
                                         "attacksRemaining": 0
                                         })
            
            self.currentRound = 0
            self.remainingTime = ""
            self.rounds = []
            for i, r in enumerate(latestApiData["warLeague"]["rounds"]):
                roundData = []
                for tag in r["warTags"]:
                    if tag != "#0":                   
                        roundWar = self._clanManager.storage.getCwlRound(tag.strip("#"))
                        if roundWar:
                            roundData.append(roundWar)
                            self._logger.debug("Found war " + tag.strip("#"))
                            
                            if roundWar["state"] == "inWar":
                                self.currentRound = i+1
                                endTime = datetime.strptime(roundWar["endTime"], '%Y%m%dT%H%M%S.000Z')
                                self.remainingTime = endTime - datetime.utcnow()
                                self.remainingTime = str(self.remainingTime).split(".")[0]
                                
                                for c in self.results["clans"]:
                                    if c["tag"] == roundWar["clan"]["tag"]:
                                        c["attacksRemaining"] = roundWar["teamSize"] - roundWar["clan"]["attacks"]
                                    if c["tag"] == roundWar["opponent"]["tag"]:
                                        c["attacksRemaining"] = roundWar["teamSize"] - roundWar["opponent"]["attacks"]
                             
                            if roundWar["state"] != "preparation":
                                for m in roundWar["clan"]["members"]:
                                    found = False
                                    for p in self.results["players"]:
                                        if m["tag"] == p["tag"]:
                                            p = self._processCWLPlayer(i, m, p, roundWar["clan"]["name"])
                                            found = True
                                            break
                                    
                                    if not found:  
                                        self.results["players"].append(self._processCWLPlayer(i, m, {}, roundWar["clan"]["name"]))
        
                                for m in roundWar["opponent"]["members"]:
                                    found = False
                                    for p in self.results["players"]:
                                        if m["tag"] == p["tag"]:
                                            p = self._processCWLPlayer(i, m, p, roundWar["opponent"]["name"])
                                            found = True
                                            break
                                    
                                    if not found:  
                                        self.results["players"].append(self._processCWLPlayer(i, m, {}, roundWar["opponent"]["name"]))
        
                            winner = ""
                            if roundWar["state"] == "warEnded":
                                if roundWar["clan"]["stars"] > roundWar["opponent"]["stars"]:
                                    winner = "clan"
                                elif roundWar["clan"]["stars"] < roundWar["opponent"]["stars"]:
                                    winner = "opponent"
                                else:
                                    if roundWar["clan"]["destructionPercentage"] > roundWar["opponent"]["destructionPercentage"]:
                                        winner = "clan"
                                    elif roundWar["clan"]["destructionPercentage"] < roundWar["opponent"]["destructionPercentage"]:
                                        winner = "opponent"
                            
                            for leagueClan in self.results["clans"]:
                                if leagueClan["tag"] == roundWar["clan"]["tag"]:
                                    leagueClan["stars"] += roundWar["clan"]["stars"]
                                    leagueClan["attacks"] += roundWar["clan"]["attacks"]
                                    leagueClan["destruction"] += roundWar["clan"]["destructionPercentage"]
                                    if winner == "clan":
                                        leagueClan["stars"] += 10
                                    
                                if leagueClan["tag"] == roundWar["opponent"]["tag"]:
                                    leagueClan["stars"] += roundWar["opponent"]["stars"]
                                    leagueClan["attacks"] += roundWar["opponent"]["attacks"]
                                    leagueClan["destruction"] += roundWar["opponent"]["destructionPercentage"]
                                    if winner == "opponent":
                                        leagueClan["stars"] += 10
                                
                                leagueClan["destruction"] = round(leagueClan["destruction"],2)
                                roundWar["clan"]["destructionPercentage"] = round(roundWar["clan"]["destructionPercentage"],2)
                                roundWar["opponent"]["destructionPercentage"] = round(roundWar["opponent"]["destructionPercentage"],2)
                            
                if len(roundData) > 0:
                    self.rounds.append(roundData)
                    
            self.results["clans"].sort(reverse=True, key=self._sortStars)
            self.results["players"].sort(reverse=True, key=self._sortCWLRank)
            
            
    def _processCWLPlayer(self, i, m, player, clan):
        player["tag"] = m["tag"]
        player["name"] = m["name"]
        player["clan"] = clan
        player["townHallLevel"] = m["townhallLevel"]
        
        if not "rounds" in player:
            player["rounds"] = {}
            
        if not "roundsIn" in player:
            player["roundsIn"] = 0
        
        warData = {}
        if "attacks" in m:
            warData["starsAttack"] = m["attacks"][0]["stars"]
            warData["destructionAttack"] = m["attacks"][0]["destructionPercentage"]
            player["roundsIn"] += 1
        else:
            warData["starsAttack"] = "-"
            
        if "bestOpponentAttack" in m:
            warData["starsDefense"] = m["bestOpponentAttack"]["stars"]
            warData["destructionDefense"] = m["bestOpponentAttack"]["destructionPercentage"]
        else:
            warData["starsDefense"] = "-"
            
        player["rounds"][str(i)] = warData
        
        totalAttackStars = totalDefenseStars = totalAttackDestruction = totalDefenseDestruction = 0
        for key,pr in player["rounds"].items():
            if "starsAttack" in pr:
                if pr["starsAttack"] != "-":
                    totalAttackStars += pr["starsAttack"]
                        
            if "starsDefense" in pr:
                if pr["starsDefense"] != "-":
                    totalDefenseStars += pr["starsDefense"]
            if "destructionAttack" in pr:
                totalAttackDestruction += pr["destructionAttack"]
            if "destructionDefense" in pr:
                totalDefenseDestruction += pr["destructionDefense"]
        
        player["totalAttackStars"] = totalAttackStars
        player["totalDefenseStars"] = totalDefenseStars
        player["totalAttackDestruction"] = totalAttackDestruction
        player["totalDefenseDestruction"] = totalDefenseDestruction
        
        player["rank"] = 30 + (3*totalAttackStars) - totalDefenseStars + player["roundsIn"]
        
        return(player)
    
    def _sortStars(self, e):
        return( e["stars"],e["destruction"])
    
    def _sortCWLRank(self, e):
        return( e["rank"],e["totalAttackStars"],e["totalAttackDestruction"])