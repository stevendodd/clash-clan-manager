from flask import Flask
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
from apscheduler.schedulers.background import BackgroundScheduler

token = ""
clanTag = ""
notesKey = ""

if os.path.exists('data/config.json'):
    f = open('data/config.json')
    c = json.load(f)
    token = c["token"]
    clanTag = c["clanTag"]
    notesKey = c["key"]

currentwar_url = "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar"
clan_url = "https://api.clashofclans.com/v1/clans/%23" + clanTag
warlog_url = "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/warlog?limit=20"

league_url = "https://api.clashofclans.com/v1/clans/%23" + clanTag + "/currentwar/leaguegroup"
league_round_url = "https://api.clashofclans.com/v1/clanwarleagues/wars/"
player_url = "https://api.clashofclans.com/v1/players/%23"

response = requests.get(clan_url, headers={'Authorization': 'Bearer ' + token})
if response.status_code != 200:
    exit(str(response) + ": Failed to get clan")

def update():
    global clan
    
    # Update current war data
    response = requests.get(currentwar_url, headers={'Authorization': 'Bearer ' + token})
    if response.json()["endTime"]:
        if len(clan["wars"])>0 and clan["wars"][0]["endTime"] == response.json()["endTime"]:
            clan["wars"][0] = response.json()
        else:
            clan["wars"].insert(0, response.json())

    clan["wars"] = trimList(clan["wars"],11)

    # Update clan data
    response = requests.get(clan_url, headers={'Authorization': 'Bearer ' + token})
    if response.json():
        clan["clan"] = response.json()
        
    # Update warlog data
    response = requests.get(warlog_url, headers={'Authorization': 'Bearer ' + token})
    if response.json():
        clan["warLog"] = response.json()
    
    processResults()
    write()

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
                        sortOrder += m["wars"][windex]
        m["sort"] =  sortOrder
        
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
    
    global page
    mytemplate = Template(filename='template.html')        
    members.sort(reverse=True, key=sortMembers)    
    page = mytemplate.render(members=members, 
                             content=content, 
                             warlog=clan["warLog"]["items"], 
                             warState=clan["warLog"]["currentState"]
                             )


def write():
    global clan
    with open('data/mydata.json', 'w') as f:
        json.dump(clan, f)
        
def read():
    if os.path.exists('data/mydata.json'):
        f = open('data/mydata.json')
        return(json.load(f))
    else:
        return({"wars": [], "members": []})

def loadContent():
    if os.path.exists('data/content.html'):
        f = open('data/content.html')
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

clan = read()
content = loadContent()
page = ""

update()

scheduler = BackgroundScheduler()
scheduler.add_job(func=update, trigger="interval", seconds=60)
scheduler.start()
# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

app = Flask(__name__)
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY

class PostForm(FlaskForm):
    post = TextAreaField('Write something')
    key = StringField()
    submit = SubmitField('Save')
    
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
            if os.path.exists('data/notes.json'):
                f = open('data/notes.json')
                c = json.load(f)
                form.post.data = c["notes"]
            else:
                form.post.data = 'hi'
                
        else:
            form.post.data = post
            
            notes = {"notes": post}
            with open('data/notes.json', 'w') as f:
                json.dump(notes, f)
        
        return render_template('post/post.html',form=form)
    
    else:
        return redirect("/", code=302)


@app.route("/",methods = ['GET'])
def hello():
    return(page)

@app.route("/clan",methods = ['GET'])
def showData():
    return(clan)