import clanManager
import cwlController
import migration

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
from logging.handlers import RotatingFileHandler
from logging.config import dictConfig
import email
from _curses import keyname


clan = {}
page = ""
cwlPage = ""
day = int(datetime.now().strftime("%d"))

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
clanManager = clanManager.ClanManager(app.logger)
cwlController = cwlController.CwlController(clanManager,app.logger)

def main():
    global clan, app

    clan = readData()
    writeJson(clanManager.backupFile,clan)
    clan["updateLock"] = False
    migration.Migration(clan,clanManager)
    update()
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=update, trigger="interval", seconds=60)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    
    SECRET_KEY = os.urandom(32)
    app.config['SECRET_KEY'] = SECRET_KEY


def update():
    global clan, day
    
    latestApiData = clanManager.api.getApiData()
    if latestApiData == "":
        return
      
    cwlController.process(latestApiData)
    
    cwlDonationMod = 0
    if clan["members"]:
        for p in cwlController.results["players"]:
            for m in clan["members"]:
                if p["tag"] == m["tag"]:
                    if "cwlRankMod" in m:
                       cwlDonationMod = m["cwlRankMod"]
            p["cwlDonationMod"] = cwlDonationMod
     
    global cwlPage
    mytemplate = Template(filename=clanManager.cwlTemplate) 

    cwlPage = mytemplate.render(cwl=latestApiData["warLeague"],
                                currentRound=cwlController.currentRound,
                                remainingTime=cwlController.remainingTime,
                                rounds=cwlController.rounds,
                                results=cwlController.results,
                                clanDetails=clanManager.clanDetails)        
    
    if obtainLock():
        try:
            day = int(datetime.now().strftime("%d"))
            dailyBackupFile = clanManager.backupFile + "." + str(day)
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
                            
                if day <= clanManager.warLeagueEndDay or "seasonEnd" not in clan:
                    clan["seasonEnd"] = False
                                
                if resetDetected and day > clanManager.warLeagueEndDay:
                    setPreviousDonations()
                           
            # Update current war data
            clanManager.storage.addWar(latestApiData["currentWar"])
                
            # Update clan data
            clan["clan"] = latestApiData["clan"]
            clan["lastUpdated"] = datetime.now().strftime("%c")
                
            # Update warlog data
            clanManager.storage.setWarLog(latestApiData["warLog"])
            
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
            writeJson(clanManager.dataFile,clan)
        finally:
            releaseLock()

def processResults():    
    members = clan["clan"]["memberList"]
    
    if len(clanManager.storage.getWars()) >= 1:
        clanManager.storage.getWarLog()["currentState"] = clanManager.storage.getWars()[0]["state"]
    else:
        clanManager.storage.getWarLog()["currentState"] = "warEnded"
    
    for m in members:
        sortOrder = 0
        m["cwlWarningPenality"] = 0
        m["townhallLevel"] = ""
        
        m["wars"] = []
        for x in range(clanManager.rankHistory):
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
        for w in clanManager.storage.getWars():
            if w["state"] == "warEnded":
                windex += 1
                for wm in w["clan"]["members"]:
                    if wm["tag"] == m["tag"]:
                        if m["townhallLevel"] == "":
                            m["townhallLevel"] = "static/townhalls/" + str(wm["townhallLevel"]) + ".png"
                            
                        if "attacks" in wm:
                            m["wars"][windex] = len(wm["attacks"])
                            if windex < clanManager.rankHistory:
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
                                
                                if windex < clanManager.rankHistory:                                   
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
                    
                if day > clanManager.warLeagueEndDay and "cwlWarning" in p:
                    p["cwlWarning"] = expireWarnings(m["name"],p["cwlWarning"],30) 
                
                if "prevDonationsReceived" in p:
                    prevDonationsReceived = p["prevDonationsReceived"]
                    prevDonation = p["prevDonation"]
                 
                m["prevDonationsReceived"] = prevDonationsReceived
                m["prevDonations"] = prevDonation  
                break
        
        donationMod = cwlRankMod = 0        
        if day <= clanManager.warLeagueEndDay or clan["seasonEnd"]:
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
    mytemplate = Template(filename=clanManager.homeTemplate)        
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
    
    page = mytemplate.render(clan=clanManager.clanDetails,
                             members=members, 
                             #content=content, 
                             warlog=clanManager.storage.getWarLog()["items"], 
                             warState=clanManager.storage.getWarLog()["currentState"],
                             lastUpdated=clan["lastUpdated"],
                             banners=getBanners()
                             )
  

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
    if os.path.exists(clanManager.dataFile):
        f = open(clanManager.dataFile)
        return(json.load(f))
    else:
        return({"members": [], "seasonEnd": False})
    
def readNotes():
    if os.path.exists(clanManager.notesDataFile):
        f = open(clanManager.notesDataFile)
        c = json.load(f)
        return(c["notes"])
    else:
        return('hi') 

def loadContent():
    if os.path.exists(clanManager.homeHeader):
        f = open(clanManager.homeHeader)
        return(f.readlines())
    else:
        return("")

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
        
    
    if key == clanManager.notesKey:
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
            
        return render_template(clanManager.warningTemplate,members=members,key=key)
    
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
    
    if key == clanManager.notesKey:
        form.key.data = key
                       
        if post == "" or not post:      
            form.post.data = readNotes()
                
        else:
            form.post.data = post    
            notes = {"notes": post}
            writeJson(clanManager.notesDataFile, notes)
        
        return render_template(clanManager.notesTemplate,form=form,key=key)
    
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
