from flask import Flask, app
from flask import request, redirect, render_template
from flask_wtf import FlaskForm
from wtforms import (StringField, TextAreaField, HiddenField, SubmitField)
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

token = ""
clanTag = ""
notesKey = ""
page = ""
updateMember = 0
day = int(datetime.now().strftime("%d"))
warLeagueEndDay = 8

clan = {}
apiUrls = {}

configFile = "data/config.json"
dataFile = "data/mydata.json"
backupFile = "data/backup/mydata_BK.json"
notesDataFile = "data/notes.json"

homeHeader = "data/content.html"
homeTemplate = "templates/home.html"
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
    global token, clanTag, notesKey, clan, app, apiUrls
    
    if os.path.exists(configFile):
        f = open(configFile)
        c = json.load(f)
        email = c["email"]
        password = c["password"]
        key_name = c["keyName"]
        clanTag = c["clanTag"]
        notesKey = c["key"]
        token = getToken(email,password,key_name)
    
    apiUrls = {
        "currentwar": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar",
        "clan": "https://api.clashofclans.com/v1/clans/%23" + clanTag,
        "warlog": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/warlog?limit=20",
        
        "league": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar/leaguegroup",
        "leagueRound": "https://api.clashofclans.com/v1/clanwarleagues/wars/",
        "player": "https://api.clashofclans.com/v1/players/%23",
        "season": "https://api.clashofclans.com/v1/goldpass/seasons/current"
    }
    
    response = requests.get(apiUrls["clan"], headers={'Authorization': 'Bearer ' + token})
    if response.status_code != 200:
        exit(str(response) + ": Failed to get clan")
     
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
    global updateMember
    
    latestSeason = {}
    response = requests.get(apiUrls["season"], headers={'Authorization': 'Bearer ' + token})
    if response.status_code == 200 and response.json():
        latestSeason = response.json()
        
    latestCurrentWar = {}
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
            "season": latestSeason,
            "currentWar": latestCurrentWar,
            "clan": latestClan,
            "warLog": latestWarLog,
            "players": latestPlayers})  
    
def update():
    global clan
    
    latestApiData = getApiData()
    
    if obtainLock():
        try:
            day = int(datetime.now().strftime("%d"))
            dailyBackupFile = backupFile + "." + str(day)
            pruneBackups()
            if not os.path.exists(dailyBackupFile):
                writeJson(dailyBackupFile,clan)
                
            # Update current Season data
            if "season" not in clan:
                clan["season"] = latestApiData["season"]
                
            if clan["season"] != latestApiData["season"]:
                setPreviousDonations()
                clan["season"] = latestApiData["season"]
            
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
                    clan["wars"] = trimList(clan["wars"],11)
                else:
                    clan["wars"] = trimList(clan["wars"],10)
                
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
                            
                        if "prevDonationsReceived" in m:
                            member["prevDonationsReceived"] = m["prevDonationsReceived"]
                            
                        if "prevDonation" in m:
                            member["prevDonation"] = m["prevDonation"]
                            
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
        m["townhallLevel"] = ""
        m["wars"] = [0,0,0,0,0,0,0,0,0,0]
        m["attackWarnings"] = 0
    
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
                             
                if "warnings" in p:                
                    removeDates = []
                    for w in p["warnings"]:
                        wdate = datetime.strptime(w, '%Y%m%dT%H%M')
                        if datetime.now() > wdate + timedelta(days=7):
                            removeDates.append(w)
                            app.logger.debug("Removing warning: " + m["name"] + " " + datetime.now().strftime('%Y%m%dT%H%M') + "> " + wdate.strftime('%Y%m%dT%H%M'))
                            
                    for w in removeDates:
                        p["warnings"].remove(w)                
                
                    m["warnings"] = m["attackWarnings"] + len(p["warnings"])
                else:
                    m["warnings"] = m["attackWarnings"]
                
                if "prevDonationsReceived" in p:
                    prevDonationsReceived = p["prevDonationsReceived"]
                    prevDonation = p["prevDonation"]
                 
                m["prevDonationsReceived"] = prevDonationsReceived
                m["prevDonations"] = prevDonation  
                break
        
        donationMod = 0        
        if day <= warLeagueEndDay:
            donationsReceived = prevDonationsReceived
            donations = prevDonation
        else:
            donationsReceived = m["donationsReceived"]
            donations = m["donations"]
            
        if abs(donationsReceived - donations) > 1500:
            donationMod = 0.1
        elif abs(donationsReceived - donations) > 1000:
            donationMod = 0.075
        elif abs(donationsReceived - donations) > 500:
            donationMod = 0.05
        elif abs(donationsReceived - donations) > 250:
            donationMod = 0.025
            
        if donations < donationsReceived:
            donationMod = donationMod * -1
            
        if donationMod >= 0:
            m["donationMod"] = "+" + str(donationMod*100) + "%"
        else:
            m["donationMod"] = "-" + str(donationMod*100*-1) + "%"

        donationMod += 1   
            
        m["rank"] = int(donationMod*rank*100)
        m["lastThreeRank"] = int(donationMod*lastThreeRank*100)

            
    global page
    content = loadContent()
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
        
    page = mytemplate.render(members=members, 
                             content=content, 
                             warlog=clan["warLog"]["items"], 
                             warState=clan["warLog"]["currentState"],
                             lastUpdated=clan["lastUpdated"]
                             )

def setPreviousDonations():
    global clan
    
    for m in clan["clan"]["memberList"]:
        for p in clan["members"]:
            if m["tag"] == p["tag"]:
                p["prevDonationsReceived"] = m["donationsReceived"]
                p["prevDonation"]= m["donations"]
                break        
    
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
            raise Exception("Couldn't obtain lock")
            return False
        
    clan["updateLock"] = True
    return True

def releaseLock():
    clan["updateLock"] = False
    
def readData():
    if os.path.exists(dataFile):
        f = open(dataFile)
        return(json.load(f))
    else:
        return({"wars": [], "members": []})
    
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

class PostForm(FlaskForm):
    post = TextAreaField('Write something')
    key = HiddenField()
    submit = SubmitField('Save')
    
class addWarningForm(FlaskForm):
    key = HiddenField()
    player = HiddenField()
    submit = SubmitField('Add Warning')

class deleteWarningForm(FlaskForm):
    key = HiddenField()
    player = HiddenField()
    date = HiddenField()
    submit = SubmitField('Delete Warning')

main()

@app.route('/warnings',methods = ['POST','GET'])
def warnings():
    global clan
    
    key = player = toggle = ""
    player = request.form.get('player')
    date = request.form.get('date')
    key = request.form.get('key')
    
    if key == notesKey:
        if obtainLock():     
            try:
                
                members = clan["clan"]["memberList"]
                                   
                if player != None:
                    for m in clan["members"]:
                        if m["tag"] == player:
                            if date is None:
                                wdate = datetime.now().strftime("%Y%m%dT%H%M")
                                if "warnings" in m:
                                    m["warnings"].append(wdate)
                                else:
                                    m["warnings"] = [wdate]
                                app.logger.debug("Add Warning " + m["name"])
                                
                            else:
                                for i, w in enumerate(m["warnings"]):
                                    if w == date:
                                        m["warnings"].pop(i)
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
                                    warningForm.submit.label.text = w
                                    warnings.append(warningForm)
                                m["manualWarnings"] = warnings
                                if len(warnings)>0:
                                    m["performanceWarning"] = True
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

@app.route("/clan",methods = ['GET'])
def showData():
    return(clan)
