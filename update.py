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
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from json import loads as json_loads
from base64 import b64decode as base64_b64decode

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
        "player": "https://api.clashofclans.com/v1/players/%23"
    }
    
    response = requests.get(apiUrls["clan"], headers={'Authorization': 'Bearer ' + token})
    if response.status_code != 200:
        exit(str(response) + ": Failed to get clan")
        
    clan = readData()
    update()
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=update, trigger="interval", seconds=60)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    
    SECRET_KEY = os.urandom(32)
    app.config['SECRET_KEY'] = SECRET_KEY

def update():
    global clan, updateMember
    
    # Update current war data
    response = requests.get(apiUrls["currentwar"], headers={'Authorization': 'Bearer ' + token})
    if "endTime" in response.json():
        if len(clan["wars"])>0 and clan["wars"][0]["endTime"] == response.json()["endTime"]:
            clan["wars"][0] = response.json()
        else:
            clan["wars"].insert(0, response.json())

    clan["wars"] = trimList(clan["wars"],11)

    # Update clan data
    response = requests.get(apiUrls["clan"], headers={'Authorization': 'Bearer ' + token})
    if response.json():
        clan["clan"] = response.json()
        clan["lastUpdated"] = datetime.now().strftime("%c")
        
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
            member["dateLastIn"] = datetime.now().strftime("%d %b %y")
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
        rank = lastThreeRank = stars = attacks = destrution = 0
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
                                stars += int(a["stars"])
                                destrution += int(a["destructionPercentage"])
                                attacks += 1
                                                                   
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
        
        if attacks > 0:
            m["averageStars"] = round(stars/attacks,1)
            m["averageDestruction"] = round(destrution/attacks)
        else:
            m["averageStars"] = 0
            m["averageDestruction"] = 0
                    
        for p in clan["members"]:
            if m["tag"] == p["tag"]:
                m["townhallLevel"] = "static/townhalls/" + str(p["townHallLevel"]) + ".png"
                m["warPreference"] = p["warPreference"]
                m["dateLastIn"] = p["dateLastIn"]
                break
        
        donationMod = 1
        donationsReceived = m["donationsReceived"]
        donations = m["donations"]
            
        if abs(donationsReceived - donations) > 250:
            if m["donationsReceived"] == 0:
                donationsReceived = 1

            donationMod = donations/donationsReceived
            if donationsReceived > 1000 or donations > 1000:
                if donationMod > 1.10:
                    donationMod = 1.10
                elif donationMod < 0.90:
                    donationMod = 0.90
            elif donationsReceived > 500 or donations > 500:
                if donationMod > 1.05:
                    donationMod = 1.05
                elif donationMod < 0.95:
                    donationMod = 0.95
            else:
                if donationMod > 1.025:
                    donationMod = 1.025
                elif donationMod < 0.975:
                    donationMod = 0.975
            
        m["rank"] = int(donationMod*rank*100)
        m["lastThreeRank"] = int(donationMod*lastThreeRank*100)
        donationMod -= 1
        if donationMod >= 0:
            m["donationMod"] = "+" + str(round(donationMod*100,1)) + "%"
        else:
            m["donationMod"] = "-" + str(round(donationMod*100*-1,1)) + "%"
            
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
                             warState=clan["warLog"]["currentState"],
                             lastUpdated=clan["lastUpdated"]
                             )

def writeJson(file,data):
    global clan
    with open(file, 'w') as f:
        json.dump(data, f)
        
def getToken(email,password,key_names):
    key_count = 1
    keys = _keys = []
    KEY_MAXIMUM = 10
    
    s = requests.Session() 
    body = {"email": email, "password": password}
    
    resp = s.post("https://developer.clashofclans.com/api/login", json=body)
    if resp.status_code == 403:
        raise InvalidCredentials(resp)
    
    print("Successfully logged into the developer site.")
    
    resp_paylaod = resp.json()
    ip = json_loads(base64_b64decode(resp_paylaod["temporaryAPIToken"].split(".")[1] + "====").decode("utf-8"))["limits"][1]["cidrs"][0].split("/")[0]
    
    print("Found IP address to be %s", ip)
    
    resp = s.post("https://developer.clashofclans.com/api/apikey/list")
    if "keys" in resp.json():
        keys = (resp.json())["keys"]
        _keys.extend(key["key"] for key in keys if key["name"] == key_names and ip in key["cidrRanges"])
    
        print("Retrieved %s valid keys from the developer site.", len(_keys))
    
        if len(_keys) < key_count:
            for key in (k for k in keys if k["name"] == key_names and ip not in k["cidrRanges"]):
                print(
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
    
        print("Creating key with data %s.", str(data))
    
        resp = s.post("https://developer.clashofclans.com/api/apikey/create", json=data)
        key = resp.json()
        print(resp.json())
        _keys.append(key["key"]["key"])
    
    if len(keys) == 10 and len(_keys) < key_count:
        print("%s keys were requested to be used, but a maximum of %s could be "
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
    
    print("Successfully initialised keys for use.")
    return(_keys[0])

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
