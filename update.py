from flask import Flask, app
from flask import request, redirect, render_template
from flask_wtf import FlaskForm
from wtforms import (StringField, TextAreaField, HiddenField, BooleanField, SubmitField)
from wtforms.validators import InputRequired, Length
from mako.template import Template
import requests
import json
import atexit
import os.path
import os
import time
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from json import loads as json_loads
from base64 import b64decode as base64_b64decode
from logging.handlers import RotatingFileHandler
from logging.config import dictConfig
import email
from _curses import keyname

token = ""
clanTag = ""
notesKey = ""
page = ""
cwlPage = ""
updateMember = 0
day = int(datetime.now().strftime("%d"))
warLeagueEndDay = 10
rankHistory = 10

clanDetails = {}
clan = {}
apiUrls = {}

configFile = "data/config.json"
dataFile = "data/mydata.json"
backupFile = "data/backup/mydata_BK.json"
notesDataFile = "data/notes.json"

homeHeader = "data/content.html"
homeTemplate = "templates/home.html"
cwlTemplate = "templates/cwl.html"
notesTemplate = "notes.html"
warningTemplate = "warning.html"

logfile = 'data/logs/clanManager.log'

dictConfig(
            {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
            'default': {
                        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
                       },
            'simpleformatter' : {
                        'format' : '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
    },
    'handlers':
    {
        'custom_handler': {
            'class' : 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename' : logfile,
            'level': 'DEBUG',
            'maxBytes': 10000000, 
            'backupCount': 5
        }
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['custom_handler']
    },
})

app = Flask(__name__)

def main():
    global token, clanDetails, clanTag, notesKey, rankHistory, clan, app, apiUrls
    
    if os.path.exists(configFile):
        f = open(configFile)
        c = json.load(f)
        email = c["email"]
        password = c["password"]
        key_name = c["keyName"]
        clanTag = c["clanTag"]
        notesKey = c["key"]
        
        if "history" in c:
            rankHistory = c["history"]
            
        token = getToken(email,password,key_name)
    
    apiUrls = {
        "currentwar": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar",
        "clan": "https://api.clashofclans.com/v1/clans/%23" + clanTag,
        "warlog": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/warlog?limit=20",
        
        "league": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar/leaguegroup",
        "leagueRound": "https://api.clashofclans.com/v1/clanwarleagues/wars/%23",
        "player": "https://api.clashofclans.com/v1/players/%23",
        "season": "https://api.clashofclans.com/v1/goldpass/seasons/current"
    }
    
    response = requests.get(apiUrls["clan"], headers={'Authorization': 'Bearer ' + token})
    if response.status_code != 200:
        exit(str(response) + ": Failed to get clan")
    
    clanDetails["name"] = response.json()["name"]
    clanDetails["tag"] = clanTag
    clanDetails["rankHistory"] = rankHistory

    clan = readData()
    writeJson(backupFile,clan)
    clan["updateLock"] = False
    update()
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=update, trigger="interval", seconds=60)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    
    SECRET_KEY = os.urandom(32)
    app.config['SECRET_KEY'] = SECRET_KEY

def getApiData():
    global updateMember, token
        
    latestCurrentWar = {}
    response = requests.get(apiUrls["currentwar"], headers={'Authorization': 'Bearer ' + token})
    
    if response.status_code == 403:
        app.logger.debug("Attempting to refresh token")
        if os.path.exists(configFile):
            c = json.load(open(configFile))
            token = getToken(c["email"],c["password"],c["keyName"])
            response = requests.get(apiUrls["currentwar"], headers={'Authorization': 'Bearer ' + token})
        
    if response.status_code == 200 and "preparationStartTime" in response.json():
        latestCurrentWar = response.json()
    
    latestClan = {}
    response = requests.get(apiUrls["clan"], headers={'Authorization': 'Bearer ' + token})
    if response.status_code == 200 and response.json():
        latestClan = response.json()
    
        response = requests.get(latestClan["badgeUrls"]["small"])
        if response.status_code == 200:
            open('static/badge.png', 'wb').write(response.content)
    else:
         app.logger.error("Couldn't load clan data from API: " + str(response.status_code))
         return("")
        
    latestWarLeague = {}
    response = requests.get(apiUrls["league"], headers={'Authorization': 'Bearer ' + token})
    if response.status_code == 200 and response.json():
        latestWarLeague = response.json()
    
    latestWarLog = {}
    response = requests.get(apiUrls["warlog"], headers={'Authorization': 'Bearer ' + token})
    if response.status_code == 200 and response.json():
        latestWarLog = response.json()
    
    latestPlayers = []
    for r in range(5):
        if updateMember >= len(latestClan["memberList"]):
                updateMember = 0
                
        playerTag = latestClan["memberList"][updateMember]["tag"].strip("#")
        response = requests.get(apiUrls["player"] + playerTag, headers={'Authorization': 'Bearer ' + token})
        if response.status_code == 200 and response.json():
            latestPlayers.append(response.json())
            updateMember += 1
            
    return({"updateMember": updateMember, 
            "currentWar": latestCurrentWar,
            "warLeague": latestWarLeague,
            "clan": latestClan,
            "warLog": latestWarLog,
            "players": latestPlayers})  
    
def update():
    global clan, day
    
    latestApiData = getApiData()
    if latestApiData == "":
        return
    
    basePath = path = "data/cwl/"
    if not os.path.exists(basePath):
        os.makedirs(basePath + "/tmp")
        
    if "season" in latestApiData["warLeague"]:
        path = path + latestApiData["warLeague"]["season"]
        if not os.path.exists(path):
            os.makedirs(path)
            
        writeJson(path + "/league.json", latestApiData["warLeague"])
        
        for r in latestApiData["warLeague"]["rounds"]:
            for tag in r["warTags"]:
                if tag != "#0":  
                    response = requests.get(apiUrls["leagueRound"] + tag.strip("#"), headers={'Authorization': 'Bearer ' + token})
                    if response.status_code == 200 and response.json():
                        writeJson(path + "/" + tag.strip("#") + ".json", response.json())
    
    latestCWL = max([os.path.join(basePath,d) for d in os.listdir(basePath) 
                     if os.path.isdir(os.path.join(basePath, d))], key=os.path.getmtime)
    
    if os.path.exists(latestCWL + "/league.json"):
        app.logger.debug("Processing " + latestCWL + "/league.json")
        f = open(latestCWL + "/league.json")
        latestApiData["warLeague"] = json.load(f) 
        
        results = {}
        results["clans"] = []
        results["players"] = []
        for leagueClan in latestApiData["warLeague"]["clans"]:
            results["clans"].append({"tag": leagueClan["tag"], 
                                     "name": leagueClan["name"],
                                     "badgeUrls": leagueClan["badgeUrls"], 
                                     "stars": 0, 
                                     "attacks": 0, 
                                     "destruction": 0,
                                     "attacksRemaining": 0
                                     })
        
        currentRound = 0
        remainingTime = ""
        rounds = []
        for i, r in enumerate(latestApiData["warLeague"]["rounds"]):
            roundData = []
            for tag in r["warTags"]:
                if tag != "#0":                   
                    roundWar = {}
                    #response = requests.get(apiUrls["leagueRound"] + tag.strip("#"), headers={'Authorization': 'Bearer ' + token})
                    #if response.status_code == 200 and response.json():
                    app.logger.debug("Looking for war " + latestCWL + "/" + tag.strip("#") + ".json")
                    if os.path.exists(latestCWL + "/" + tag.strip("#") + ".json"):
                        #roundWar = response.json()
                        #writeJson(path + "/" + tag.strip("#") + ".json", roundWar)
                        f = open(latestCWL + "/" + tag.strip("#") + ".json")
                        roundWar = json.load(f)
                        roundData.append(roundWar)
                        app.logger.debug("Found war " + tag.strip("#"))
                        
                        if roundWar["state"] == "inWar":
                            currentRound = i+1
                            endTime = datetime.strptime(roundWar["endTime"], '%Y%m%dT%H%M%S.000Z')
                            remainingTime = endTime - datetime.utcnow()
                            remainingTime = str(remainingTime).split(".")[0]
                            
                            for c in results["clans"]:
                                if c["tag"] == roundWar["clan"]["tag"]:
                                    c["attacksRemaining"] = roundWar["teamSize"] - roundWar["clan"]["attacks"]
                                if c["tag"] == roundWar["opponent"]["tag"]:
                                    c["attacksRemaining"] = roundWar["teamSize"] - roundWar["opponent"]["attacks"]
                         
                        if roundWar["state"] != "preparation":
                            for m in roundWar["clan"]["members"]:
                                found = False
                                for p in results["players"]:
                                    if m["tag"] == p["tag"]:
                                        p = processCWLPlayer(i, m, p, roundWar["clan"]["name"])
                                        found = True
                                        break
                                
                                if not found:  
                                    results["players"].append(processCWLPlayer(i, m, {}, roundWar["clan"]["name"]))
    
                            for m in roundWar["opponent"]["members"]:
                                found = False
                                for p in results["players"]:
                                    if m["tag"] == p["tag"]:
                                        p = processCWLPlayer(i, m, p, roundWar["opponent"]["name"])
                                        found = True
                                        break
                                
                                if not found:  
                                    results["players"].append(processCWLPlayer(i, m, {}, roundWar["opponent"]["name"]))
    
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
                        
                        for leagueClan in results["clans"]:
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
                rounds.append(roundData)
        
        cwlDonationMod = 0
        if clan["members"]:
            for p in results["players"]:
                for m in clan["members"]:
                    if p["tag"] == m["tag"]:
                        if "cwlRankMod" in m:
                           cwlDonationMod = m["cwlRankMod"]
                p["cwlDonationMod"] = cwlDonationMod
        
        results["clans"].sort(reverse=True, key=sortStars)
        results["players"].sort(reverse=True, key=sortCWLRank)
        
        global cwlPage
        mytemplate = Template(filename=cwlTemplate) 
    
        cwlPage = mytemplate.render(cwl=latestApiData["warLeague"],
                                    currentRound=currentRound,
                                    remainingTime=remainingTime,
                                    rounds=rounds,
                                    results=results,
                                    clanDetails=clanDetails)        
    
    if obtainLock():
        try:
            day = int(datetime.now().strftime("%d"))
            dailyBackupFile = backupFile + "." + str(day)
            pruneBackups()
            if not os.path.exists(dailyBackupFile):
                writeJson(dailyBackupFile,clan)
                
            # Detect donation reset
            if "clan" in clan:
                resetDetected = False
                rcounter = 0
                for ml in latestApiData["clan"]["memberList"]:
                    if (not resetDetected) and ml["donationsReceived"] == 0 and ml["donations"] == 0:
                        for m in clan["clan"]["memberList"]:
                            if m["tag"] == ml["tag"]:
                                if m["donationsReceived"] > 0 or m["donations"] > 0:
                                    rcounter += 1
                                    break
                                    
                            if rcounter >= 5:
                                resetDetected = True
                                break
                            
                if day <= warLeagueEndDay or "seasonEnd" not in clan:
                    clan["seasonEnd"] = False
                                
                if resetDetected and day > warLeagueEndDay:
                    setPreviousDonations()
                           
            # Update current war data
            if "preparationStartTime" in latestApiData["currentWar"]:
                if len(clan["wars"])>0 and clan["wars"][0]["preparationStartTime"] == latestApiData["currentWar"]["preparationStartTime"]:
                    clan["wars"][0] = latestApiData["currentWar"]
                else:                       
                    clan["wars"].insert(0, latestApiData["currentWar"])
                    
            for i, w in enumerate(clan["wars"]):
                if w["state"] == "preparation" and i>0:
                    app.logger.debug('delete: ' + clan["wars"][i]['state'])
                    clan["wars"].pop(i)
                else:
                    if w["state"] == "inWar" and i>0:
                        w["state"] = "warEnded"
                           
                    app.logger.debug('keep: ' + clan["wars"][i]['state'] + " " + clan["wars"][i]['endTime'])
            
            # Only keep last 10 wars
            if len(clan["wars"]) > 0:
                if clan["wars"][0]['state'] != "warEnded":       
                    clan["wars"] = trimList(clan["wars"],rankHistory+1)
                else:
                    clan["wars"] = trimList(clan["wars"],rankHistory)
                
            # Update clan data
            clan["clan"] = latestApiData["clan"]
            clan["lastUpdated"] = datetime.now().strftime("%c")
                
            # Update warlog data
            clan["warLog"] = latestApiData["warLog"]
            
            # Update player
            for j,player in enumerate(latestApiData["players"]):
                currentMember = latestApiData["updateMember"] - len(latestApiData["players"]) + j
                if currentMember < 0:
                    currentMember = len(clan["clan"]["memberList"]) + currentMember
                         
                member = {
                    "tag": player["tag"],
                    "name": player["name"],
                    "townHallLevel": player["townHallLevel"],
                    "warPreference": player["warPreference"],
                    "dateLastIn": "",
                    "dateLastSeen": datetime.now().strftime("%d %b %y")
                }
                
                if member["warPreference"] == "in":
                    member["dateLastIn"] = datetime.now().strftime("%d %b")                
                
                found = False    
                for i,m in enumerate(clan["members"]):
                    if m["tag"] == member["tag"]:
                        if member["warPreference"] == "out":
                            member["dateLastIn"] = m["dateLastIn"]
                            
                        if "warnings" in m:
                            member["warnings"] = m["warnings"]
                            
                        if "cwlWarning" in m:
                            member["cwlWarning"] = m["cwlWarning"]
                            
                        if "prevDonationsReceived" in m:
                            member["prevDonationsReceived"] = m["prevDonationsReceived"]
                            
                        if "prevDonation" in m:
                            member["prevDonation"] = m["prevDonation"]
                            
                        if "cwlRankMod" in m:
                            member["cwlRankMod"] = m["cwlRankMod"]
                            
                        app.logger.debug("Updating [" + str(currentMember + 1) + "|" + str(len(clan["clan"]["memberList"])) + "] " + clan["clan"]["memberList"][currentMember]["name"] + ": " + str(member))
                        clan["members"][i] = member
                        found = True
                        break
                
                if not found:
                    app.logger.debug("Adding [" + str(currentMember + 1) + "|" + str(len(clan["clan"]["memberList"])) + "] " + clan["clan"]["memberList"][currentMember]["name"] + ": " + str(member))
                    clan["members"].append(member)
                                
            processResults()
            writeJson(dataFile,clan)
        finally:
            releaseLock()

def processResults():    
    members = clan["clan"]["memberList"]
    
    if len(clan["wars"]) >= 1:
        clan["warLog"]["currentState"] = clan["wars"][0]["state"]
    else:
        clan["warLog"]["currentState"] = "warEnded"
    
    for m in members:
        sortOrder = 0
        m["cwlWarningPenality"] = 0
        m["townhallLevel"] = ""
        
        m["wars"] = []
        for x in range(rankHistory):
            m["wars"].append(0)
            
        m["attackWarnings"] = 0
        
        if "prevDonations" not in m:
            m["prevDonations"] = 0
            m["prevDonationsReceived"] = 0
    
        if m["role"] == "leader":
            m["role"] = "L"
        elif m["role"] == "member":
            m["role"] = "M"    
        elif m["role"] == "coLeader":
            m["role"] = "CL"
        elif m["role"] == "admin":
            m["role"] = "E"
         
        windex=-1
        rank = lastThreeRank = stars = attacks = destrution = missedAttackCounter = 0
        for w in clan["wars"]:
            if w["state"] == "warEnded":
                windex += 1
                for wm in w["clan"]["members"]:
                    if wm["tag"] == m["tag"]:
                        if m["townhallLevel"] == "":
                            m["townhallLevel"] = "static/townhalls/" + str(wm["townhallLevel"]) + ".png"
                            
                        if "attacks" in wm:
                            m["wars"][windex] = len(wm["attacks"])
                            if windex < rankHistory:
                                rank += m["wars"][windex]
                            
                            if len(wm["attacks"]) == 1:
                                wdate = datetime.strptime(w["endTime"], '%Y%m%dT%H%M%S.000Z')
                                if datetime.now() < wdate + timedelta(days=7):
                                    missedAttackCounter +=1
                                    
                                    if missedAttackCounter == 2:
                                        missedAttackCounter = 0
                                        m["attackWarnings"] += 1                                   
                            
                            for a in wm["attacks"]:
                                dTownhallLevel = 0
                                dMapPosition = 0
                                for o in w["opponent"]["members"]:
                                    if o["tag"] == a["defenderTag"]: 
                                        dTownhallLevel = o["townhallLevel"]
                                        dMapPosition = o["mapPosition"]
                                        break
                                    
                                thm = 1
                                if wm["townhallLevel"] < dTownhallLevel:
                                    thm = 1.2
                                bonus = thm * ((int(a["stars"])*0.1) + (int(a["destructionPercentage"])/400))
                                stars += int(a["stars"])
                                destrution += int(a["destructionPercentage"])
                                attacks += 1
                                
                                if windex < rankHistory:                                   
                                    if wm["mapPosition"] - dMapPosition > -3:
                                        rank += bonus
                                    else:
                                        rank += bonus * 0.75   

                        else:
                            m["wars"][windex] = -1
                            
                            wdate = datetime.strptime(w["endTime"], '%Y%m%dT%H%M%S.000Z')
                            if datetime.now() < wdate + timedelta(days=7):
                                m["attackWarnings"] += 1                                    
                            
                        if windex < 2:
                            lastThreeRank = rank
                            
                        sortOrder += m["wars"][windex]
        m["sort"] =  sortOrder
        
        if attacks > 0:
            m["averageStars"] = round(stars/attacks,1)
            m["averageDestruction"] = round(destrution/attacks)
        else:
            m["averageStars"] = 0
            m["averageDestruction"] = 0
        
        prevDonationsReceived = 0
        prevDonation = 0
        for p in clan["members"]:
            if m["tag"] == p["tag"]:
                m["townhallLevel"] = "static/townhalls/" + str(p["townHallLevel"]) + ".png"
                m["warPreference"] = p["warPreference"]
                m["dateLastIn"] = p["dateLastIn"]
                
                if "cwlWarning" in p:
                    if len(p["cwlWarning"]) > 0:
                        m["cwlWarningPenality"] = 500
                             
                if "warnings" in p:
                    p["warnings"] = expireWarnings(m["name"],p["warnings"],7)                      
                
                    m["warnings"] = m["attackWarnings"] + len(p["warnings"])
                else:
                    m["warnings"] = m["attackWarnings"]
                    
                if day > warLeagueEndDay and "cwlWarning" in p:
                    p["cwlWarning"] = expireWarnings(m["name"],p["cwlWarning"],30) 
                
                if "prevDonationsReceived" in p:
                    prevDonationsReceived = p["prevDonationsReceived"]
                    prevDonation = p["prevDonation"]
                 
                m["prevDonationsReceived"] = prevDonationsReceived
                m["prevDonations"] = prevDonation  
                break
        
        donationMod = cwlRankMod = 0        
        if day <= warLeagueEndDay or clan["seasonEnd"]:
            donationsReceived = prevDonationsReceived
            donations = prevDonation
        else:
            donationsReceived = m["donationsReceived"]
            donations = m["donations"]

        m["donationMod"] = "+" + str(int(donations/100))
        p["cwlRankMod"] = int(donations/2000)
        if p["cwlRankMod"] > 6:
            p["cwlRankMod"] = 6
            
        m["rank"] = int((donations/100)+(rank*100)) - m["cwlWarningPenality"]
        m["lastThreeRank"] = int((donations/100)+(lastThreeRank*100))
        
        if m["rank"] < 0:
            m["rank"] = 0
            
    global page
    mytemplate = Template(filename=homeTemplate)        
    members.sort(reverse=True, key=sortMembers)
    
    # Has rank improved in last three wars
    lastThreeMembers = members.copy()
    lastThreeMembers.sort(reverse=True, key=sortMembersLastThree)
    
    for i,m in enumerate(members):
        m["lastThree"] = 0
        for j,lt in enumerate(lastThreeMembers):
            if m["tag"] == lt["tag"]:
                if i > j:
                    m["lastThree"] = 1
                elif i < j:
                    m["lastThree"] = -1
                break
    
    page = mytemplate.render(clan=clanDetails,
                             members=members, 
                             #content=content, 
                             warlog=clan["warLog"]["items"], 
                             warState=clan["warLog"]["currentState"],
                             lastUpdated=clan["lastUpdated"],
                             banners=getBanners()
                             )

def processCWLPlayer(i, m, player, clan):
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

def setPreviousDonations():
    global clan
    
    clan["seasonEnd"] = True
    for m in clan["clan"]["memberList"]:
        for p in clan["members"]:
            if m["tag"] == p["tag"]:
                p["prevDonationsReceived"] = m["donationsReceived"]
                p["prevDonation"]= m["donations"]
                break        

def expireWarnings(player,warnings,t):
    removeDates = []
    for w in warnings:
        wdate = datetime.strptime(w, '%Y%m%dT%H%M')
        if datetime.now() > wdate + timedelta(days=t):
            removeDates.append(w)
            app.logger.debug("Removing warning: " + player + " " + datetime.now().strftime('%Y%m%dT%H%M') + "> " + wdate.strftime('%Y%m%dT%H%M'))
            
    for w in removeDates:
        warnings.remove(w)     
    
    return(warnings)

def writeJson(file,data):
    global clan
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def pruneBackups():
    path = "data/backup"
    now = time.time()

    for filename in os.listdir(path):
        # if os.stat(os.path.join(path, filename)).st_mtime < now - 7 * 86400:
        if os.path.getmtime(os.path.join(path, filename)) < now - 7 * 86400:
            if os.path.isfile(os.path.join(path, filename)):
                os.remove(os.path.join(path, filename))
                
def getBanners():
    path = "static/banners"
    banners = []
    
    for filename in os.listdir(path):
        banners.append(filename)
        
    return(banners)
        
        
def getToken(email,password,key_names):
    key_count = 1
    keys = _keys = []
    KEY_MAXIMUM = 10
    
    s = requests.Session() 
    body = {"email": email, "password": password}
    
    resp = s.post("https://developer.clashofclans.com/api/login", json=body)
    if resp.status_code == 403:
        raise InvalidCredentials(resp)
    
    app.logger.debug("Successfully logged into the developer site.")
    
    resp_paylaod = resp.json()
    ip = json_loads(base64_b64decode(resp_paylaod["temporaryAPIToken"].split(".")[1] + "====").decode("utf-8"))["limits"][1]["cidrs"][0].split("/")[0]
    
    app.logger.debug("Found IP address to be %s", ip)
    
    resp = s.post("https://developer.clashofclans.com/api/apikey/list")
    if "keys" in resp.json():
        keys = (resp.json())["keys"]
        _keys.extend(key["key"] for key in keys if key["name"] == key_names and ip in key["cidrRanges"])
    
        app.logger.debug("Retrieved %s valid keys from the developer site.", len(_keys))
    
        if len(_keys) < key_count:
            for key in (k for k in keys if k["name"] == key_names and ip not in k["cidrRanges"]):
                app.logger.debug(
                    "Deleting key with the name %s and IP %s (not matching our current IP address).",
                    key_names, key["cidrRanges"],
                )
                s.post("https://developer.clashofclans.com/api/apikey/revoke", json={"id": key["id"]})
    
    while len(_keys) < key_count and len(keys) < KEY_MAXIMUM:
        data = {
            "name": key_names,
            "description": "Created on {}".format(datetime.now().strftime("%c")),
            "cidrRanges": [ip],
            "scopes": ["clash"],
        }
    
        app.logger.debug("Creating key with data %s.", str(data))
    
        resp = s.post("https://developer.clashofclans.com/api/apikey/create", json=data)
        key = resp.json()
        app.logger.debug(resp.json())
        _keys.append(key["key"]["key"])
    
    if len(keys) == 10 and len(_keys) < key_count:
        app.logger.debug("%s keys were requested to be used, but a maximum of %s could be "
                     "found/made on the developer site, as it has a maximum of 10 keys per account. "
                     "Please delete some keys or lower your `key_count` level."
                     "I will use %s keys for the life of this client.",
                     key_count, len(_keys), len(_keys))
    
    if len(_keys) == 0:
        raise RuntimeError(
            "There are {} API keys already created and none match a key_name of '{}'."
            "Please specify a key_name kwarg, or go to 'https://developer.clashofclans.com' to delete "
            "unused keys.".format(len(keys), key_names)
        )
    
    app.logger.debug("Successfully initialised keys for use.")
    return(_keys[0])

def obtainLock():
    count = 0
    while clan["updateLock"]:
        time.sleep(1)
        count += 1
        
        if count > 10:
            #raise Exception("Couldn't obtain lock")
            #return False
            break
        
    clan["updateLock"] = True
    return True

def releaseLock():
    clan["updateLock"] = False
    
def readData():
    if os.path.exists(dataFile):
        f = open(dataFile)
        return(json.load(f))
    else:
        return({"wars": [], "members": [], "seasonEnd": False})
    
def readNotes():
    if os.path.exists(notesDataFile):
        f = open(notesDataFile)
        c = json.load(f)
        return(c["notes"])
    else:
        return('hi') 

def loadContent():
    if os.path.exists(homeHeader):
        f = open(homeHeader)
        return(f.readlines())
    else:
        return("")

def trimList(list, size):
    n = len(list)
    for i in range(0, n - size ):
        list.pop()
    return(list)

def sortMembers(e):
    return e["rank"]

def sortMembersLastThree(e):
    return e["lastThreeRank"]

def sortStars(e):
    return( e["stars"],e["destruction"])

def sortCWLRank(e):
    return( e["rank"],e["totalAttackStars"],e["totalAttackDestruction"])

class PostForm(FlaskForm):
    post = TextAreaField('Write something')
    key = HiddenField()
    submit = SubmitField('Save')
    
class addWarningForm(FlaskForm):
    key = HiddenField()
    player = HiddenField()
    type = BooleanField('CWL')
    submit = SubmitField('Add Warning')

class deleteWarningForm(FlaskForm):
    key = HiddenField()
    player = HiddenField()
    date = HiddenField()
    type = HiddenField()
    submit = SubmitField('Delete Warning')

main()

@app.route('/warnings',methods = ['POST','GET'])
def warnings():
    global clan
    
    key = player = toggle = ""
    player = request.form.get('player')
    date = request.form.get('date')
    cwlWarning = request.form.get('type')
    key = request.form.get('key')
    app.logger.debug("Warning form; " + str(request.form.to_dict(flat=False)))
        
    
    if key == notesKey:
        if obtainLock():     
            try:  
                members = clan["clan"]["memberList"]
                                   
                if player != None:
                    for p in clan["members"]:
                        if p["tag"] == player:
                            if date is None:
                                wdate = datetime.now().strftime("%Y%m%dT%H%M")
                                if cwlWarning == "y":
                                    if "cwlWarning" in p:
                                        p["cwlWarning"].append(wdate)
                                    else:
                                        p["cwlWarning"] = [wdate]
                                    app.logger.debug("Add CWL Warning " + p["name"])

                                if "warnings" in p:
                                    p["warnings"].append(wdate)
                                else:
                                    p["warnings"] = [wdate]
                                app.logger.debug("Add Warning " + p["name"])
                                
                            else:
                                if cwlWarning == "y":
                                    for i, w in enumerate(p["cwlWarning"]):
                                        if w == date:
                                            app.logger.debug("Removing CWL Warning " + p["name"] + " " + date)
                                            p["cwlWarning"].pop(i)
                                            break
                                else:
                                    for i, w in enumerate(p["warnings"]):
                                        if w == date:
                                            app.logger.debug("Removing Warning " + p["name"] + " " + date)
                                            p["warnings"].pop(i)
                                            break
                                
                    for m in members:
                        if m["tag"] == player:
                            if date is None:
                                m["warnings"] += 1
                            else:
                                m["warnings"] -= 1
                            
                for m in members:
                    form = addWarningForm()
                    form.key.data = key
                    form.player.data = m["tag"]
                    form.type.data = False
                    m["form"] = form
                    m["performanceWarning"] = False
                    warnings = []
                    for p in clan["members"]:
                        if m["tag"] == p["tag"]:
                            if "warnings" in p:
                                for w in p["warnings"]:
                                    warningForm = deleteWarningForm()
                                    warningForm.key.data = key
                                    warningForm.player.data = m["tag"]
                                    warningForm.date.data = w
                                    warningForm.type.data = False
                                    warningForm.submit.label.text = w
                                    warnings.append(warningForm)                             
                                
                                if len(warnings)>0:
                                    m["performanceWarning"] = True
                                    
                            if "cwlWarning" in p:
                                for w in p["cwlWarning"]:
                                    warningForm = deleteWarningForm()
                                    warningForm.key.data = key
                                    warningForm.player.data = m["tag"]
                                    warningForm.date.data = w
                                    warningForm.type.data = "y"
                                    warningForm.submit.label.text = "CWL Warning"
                                    warnings.append(warningForm)                                

                            m["manualWarnings"] = warnings
                            break
            finally:
                releaseLock()
            
        return render_template(warningTemplate,members=members,key=key)
    
    else:
        return redirect("/", code=302)
    
@app.route('/post',methods = ['POST','GET'])
def post():
    form = PostForm()
    
    post = ""
    key = ""
    if request.method == 'POST':
        post = request.form.get('post')
        key = request.form.get('key')
    
    if key == notesKey:
        form.key.data = key
                       
        if post == "" or not post:      
            form.post.data = readNotes()
                
        else:
            form.post.data = post    
            notes = {"notes": post}
            writeJson(notesDataFile, notes)
        
        return render_template(notesTemplate,form=form,key=key)
    
    else:
        return redirect("/", code=302)

@app.route("/",methods = ['GET'])
def hello():
    return(page)

@app.route("/cwl",methods = ['GET'])
def cwl():
    return(cwlPage)

@app.route("/clan",methods = ['GET'])
def showData():
    return(clan)
