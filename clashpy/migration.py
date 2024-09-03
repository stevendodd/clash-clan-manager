import shutil
import os.path


class Migration:
    
    def __init__(self, clan, clanManager):
        self._clanManager = clanManager
        self._clan = clan
        self.migrateCwl()
        self.migrateWars()
        self.migrateMembers()
        
        
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