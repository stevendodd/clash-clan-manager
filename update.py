from flask import Flask, app
from flask import request, redirect, render_template
from flask_wtf import FlaskForm
from wtforms import (StringField, TextAreaField, SubmitField)
from wtforms.validators import InputRequired, Length
from mako.template import Template
import requests
import json
import atexit
import os.path
import os
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

token = ""
clanTag = ""
notesKey = ""
page = ""
updateMember = 0

clan = {}
apiUrls = {}

configFile = "data/config.json"
dataFile = "data/mydata.json"
notesDataFile = "data/notes.json"

homeHeader = "data/content.html"
homeTemplate = "templates/home.html"
notesTemplate = "notes.html"

app = Flask(__name__)

def main():
    global token, clanTag, notesKey, clan, app, apiUrls
    
    if os.path.exists(configFile):
        f = open(configFile)
        c = json.load(f)
        token = c["token"]
        clanTag = c["clanTag"]
        notesKey = c["key"]
    
    apiUrls = {
        "currentwar": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar",
        "clan": "https://api.clashofclans.com/v1/clans/%23" + clanTag,
        "warlog": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/warlog?limit=20",
        
        "league": "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar/leaguegroup",
        "leagueRound": "https://api.clashofclans.com/v1/clanwarleagues/wars/",
        "player": "https://api.clashofclans.com/v1/players/%23"
    }
    
    clan = readData()
    update()
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=update, trigger="interval", seconds=60)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    
    SECRET_KEY = os.urandom(32)
    app.config['SECRET_KEY'] = SECRET_KEY

    response = requests.get(apiUrls["clan"], headers={'Authorization': 'Bearer ' + token})
    if response.status_code != 200:
        exit(str(response) + ": Failed to get clan")

def update():
    global clan, updateMember
    
    # Update current war data
    response = requests.get(apiUrls["currentwar"], headers={'Authorization': 'Bearer ' + token})
    if response.json()["endTime"]:
        if len(clan["wars"])>0 and clan["wars"][0]["endTime"] == response.json()["endTime"]:
            clan["wars"][0] = response.json()
        else:
            clan["wars"].insert(0, response.json())

    clan["wars"] = trimList(clan["wars"],11)

    # Update clan data
    response = requests.get(apiUrls["clan"], headers={'Authorization': 'Bearer ' + token})
    if response.json():
        clan["clan"] = response.json()
        
    # Update warlog data
    response = requests.get(apiUrls["warlog"], headers={'Authorization': 'Bearer ' + token})
    if response.json():
        clan["warLog"] = response.json()
    
    # Update player
    playerTag = clan["clan"]["memberList"][updateMember]["tag"].strip("#")
    response = requests.get(apiUrls["player"] + playerTag, headers={'Authorization': 'Bearer ' + token})
    if response.json():
        player = response.json()
        
        member = {
            "tag": player["tag"],
            "townHallLevel": player["townHallLevel"],
            "warPreference": player["warPreference"]
        }
        
        if member["warPreference"] == "in":
            member["dateLastIn"] = datetime.datetime.now().strftime("%d %b %y")
        else:
            member["dateLastIn"] = ""
        
        found = False    
        for m in clan["members"]:
            if m["tag"] == member["tag"]:
                if member["warPreference"] == "out":
                    member["dateLastIn"] = m["dateLastIn"]
                m = member.copy()
                found = True
        
        if not found:
            clan["members"].append(member)
        
        updateMember += 1
        if updateMember == len(clan["clan"]["memberList"]):
            updateMember = 0
    
    processResults()
    writeJson(dataFile,clan)

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
        
        if m["role"] == "leader":
            m["role"] = "L"
        elif m["role"] == "member":
            m["role"] = "M"    
        elif m["role"] == "coLeader":
            m["role"] = "CL"
        elif m["role"] == "admin":
            m["role"] = "E"
         
        windex=-1
        rank=0
        lastThreeRank=0
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
                                                                        
                                if wm["mapPosition"] - dMapPosition > -3:
                                    rank += bonus
                                else:
                                    rank += bonus * 0.75   

                        else:
                            m["wars"][windex] = -1
                            
                        if windex < 2:
                            lastThreeRank = rank
                            
                        sortOrder += m["wars"][windex]
        m["sort"] =  sortOrder
        
        for p in clan["members"]:
            if m["tag"] == p["tag"]:
                m["townhallLevel"] = "static/townhalls/" + str(p["townHallLevel"]) + ".png"
                m["warPreference"] = p["warPreference"]
                m["dateLastIn"] = p["dateLastIn"]
                break
        
        donationMod = 1
        donationsReceived = m["donationsReceived"]
        if m["donationsReceived"] == 0:
            donationsReceived = 1
            
        donationMod = m["donations"]/donationsReceived
        if donationMod > 1.10:
            donationMod = 1.10
        elif donationMod < 0.90:
            donationMod = 0.90
            
        m["rank"] = int(donationMod*rank*100)
        m["lastThreeRank"] = int(donationMod*lastThreeRank*100)
    
    global page
    content = loadContent()
    mytemplate = Template(filename=homeTemplate)        
    members.sort(reverse=True, key=sortMembers)
    
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
                             warState=clan["warLog"]["currentState"]
                             )

def writeJson(file,data):
    global clan
    with open(file, 'w') as f:
        json.dump(data, f)
        
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
    key = StringField()
    submit = SubmitField('Save')

main()
    
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
        
        return render_template(notesTemplate,form=form)
    
    else:
        return redirect("/", code=302)

@app.route("/",methods = ['GET'])
def hello():
    return(page)

@app.route("/clan",methods = ['GET'])
def showData():
    return(clan)
