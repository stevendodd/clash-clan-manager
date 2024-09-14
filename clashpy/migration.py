import shutil
import os.path
from datetime import datetime

import utils

class Migration:
    
    def __init__(self, clan, clanManager):
        self._clanManager = clanManager
        self._clan = clan
        self.migrateCwl()
        self.migrateWars()
        self.migrateMembers()
        self.pruneMembers()
        self.migrateDonations()
        
        
    def migrateCwl(self):
        original = "data/cwl"
        target = "data/api"
        if os.path.exists(original):
            if os.path.exists(target + "/cwl"):
                shutil.rmtree(target + "/cwl")
            shutil.move(original, target)
            
            
    def migrateWars(self):
        if "wars" in self._clan:
            basePath = "data/api/war/"
            for w in self._clan["wars"]:
                warFileName = basePath + w["preparationStartTime"] + ".json"
                self._clanManager.storage.writeJson(warFileName,w)
                
            del self._clan["wars"]
            
        if "warLog" in self._clan:
            del self._clan["warLog"]
            
    def migrateMembers(self):
        if "members" in self._clan:
            memberFile = "data/members/members.json"
            
            for m in self._clan["members"]:
                if "prevDonation" in m:
                    m["prevDonations"] = m["prevDonation"]
                    del m["prevDonation"]
            
            self._clanManager.storage.writeJson(memberFile,self._clan["members"])
            self._clanManager.storage._loadMembers()
                
            del self._clan["members"]


    def pruneMembers(self):
        year = int(datetime.now().strftime("%y")) - 1
        for m in self._clanManager.storage.getMembers():
            if "dateLastSeen" not in m:
                self._clanManager.storage.archiveMember(m)
                
            else:
                if int(m["dateLastSeen"][-2:]) < year:
                    self._clanManager.storage.archiveMember(m)


            
    def migrateDonations(self):
        currentSeason = utils.getCurrentSeason()
        previousSeason = utils.getPreviousSeason()
        clan = self._clanManager.api.getClan()
        currentMembers = clan["memberList"]
        
        for member in currentMembers:
            m = self._clanManager.storage.getMember(member["tag"])
                        
            if "donationHistory" not in m:
                m = utils.addDonationHistory(m,currentSeason,previousSeason)       
                
                if "donations" in m:    
                    m["donationHistory"][currentSeason]["donations"] = m["donations"]
                    
                if "donationsReceived" in m:
                    m["donationHistory"][currentSeason]["donationsReceived"] = m["donationsReceived"]
                
                if "prevDonations" in m:
                    m["donationHistory"][previousSeason]["donations"] = m["prevDonations"]
                    del m["prevDonations"]
                    
                if "prevDonationsReceived" in m:
                    m["donationHistory"][previousSeason]["donationsReceived"] = m["prevDonationsReceived"]
                    del m["prevDonationsReceived"]
            
                self._clanManager.storage.updateMembers([m])