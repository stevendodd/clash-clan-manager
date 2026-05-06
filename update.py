import clanManager
import cwlController
import migration
import utils
import hmac
import appState

from flask import Flask, jsonify
from flask import request, redirect, render_template
from flask_wtf import FlaskForm
from wtforms import (TextAreaField, HiddenField, BooleanField, SubmitField)
from mako.template import Template
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


logfile = 'data/logs/clanManager.log'
utils.touch(logfile)

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
cwlController = cwlController.CwlController(clanManager, app.logger)
state = None


def main():
    global state
    state = appState.AppState(clanManager, clanManager.storage.writeJson, app.logger)
    state.init_clan(readData())
    clanManager.storage.writeJson(clanManager.backupFile, state.get_clan_ref())
    migration.Migration(state.get_clan_ref(), clanManager)
    update()

    scheduler = BackgroundScheduler()
    scheduler.add_job(func=update, trigger="interval", seconds=60)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))


def update():
    latestApiData = clanManager.api.getApiData()
    if latestApiData == "":
        return

    cwlController.process(latestApiData)

    rendered_cwlPage = None
    if cwlController.results is not None:
        cwlDonationMod = 0
        if clanManager.storage.getMembers():
            for p in cwlController.results["players"]:
                for m in clanManager.storage.getMembers():
                    if p["tag"] == m["tag"]:
                        if "cwlRankMod" in m:
                           cwlDonationMod = m["cwlRankMod"]
                p["cwlDonationMod"] = cwlDonationMod

        mytemplate = Template(filename=clanManager.cwlTemplate)

        rendered_cwlPage = mytemplate.render(cwl=latestApiData["warLeague"],
                                    currentRound=cwlController.currentRound,
                                    remainingTime=cwlController.remainingTime,
                                    rounds=cwlController.rounds,
                                    results=cwlController.results,
                                    clanDetails=clanManager.clanDetails)

    dailyBackupFile = clanManager.backupFile + "." + str(state.get_day())
    pruneBackups()
    if not os.path.exists(dailyBackupFile):
        clanManager.storage.writeJson(dailyBackupFile, state.get_clan_snapshot())

    clanManager.storage.addWar(latestApiData["currentWar"])

    clanManager.storage.setWarLog(latestApiData["warLog"])

    latestPlayers = []
    for j, player in enumerate(latestApiData["players"]):
        currentMember = latestApiData["updateMember"] - len(latestApiData["players"]) + j
        if currentMember < 0:
            currentMember = len(state.get_member_list()) + currentMember

        player["dateLastSeen"] = datetime.now().strftime("%d %b %y")
        player["currentMemberNumber"] = currentMember

        if player["warPreference"] == "in":
            player["dateLastIn"] = datetime.now().strftime("%d %b")

        latestPlayers.append(player)

    clanManager.storage.updateMembers(latestPlayers)

    state.begin_update(latestApiData)
    processResults(state)
    state.finish_update(rendered_cwlPage)


def processResults(st):
    currentSeason = utils.getCurrentSeason()
    previousSeason = utils.getPreviousSeason()
    seasonEnd = utils.getSeasonEndDay()

    currentMembers = st.get_member_list()

    if len(clanManager.storage.getWars()) >= 1:
        clanManager.storage.getWarLog()["currentState"] = clanManager.storage.getWars()[0]["state"]
    else:
        clanManager.storage.getWarLog()["currentState"] = "warEnded"

    members = []
    day = st.get_day()
    for m in currentMembers:
        member = clanManager.storage.getMember(m["tag"])

        sortOrder = 0
        member["name"] = m["name"]
        member["donationsReceived"] = m["donationsReceived"]
        member["donations"] = m["donations"]
        member["townhallImage"] = "static/townhalls/" + str(m["townHallLevel"]) + ".png"
        member["league"] = m["league"]
        member["warningCount"] = 0

        member["wars"] = []
        for x in range(clanManager.rankHistory):
            member["wars"].append(0)

        if "donationHistory" not in member:
            member = utils.addDonationHistory(member, currentSeason, previousSeason)

        if currentSeason not in member["donationHistory"]:
            member["donationHistory"][currentSeason] = {
               "donations": 0,
               "donationsReceived": 0,
               "savedDonations": 0,
               "savedDonationsReceived": 0
            }

        if m["donations"] < member["donationHistory"][currentSeason]["donations"] and day != seasonEnd:
            app.logger.debug("Saving donations for {} - donations: {} saved: +{}".format(
                    member["name"],
                    m["donations"],
                    member["donationHistory"][currentSeason]["donations"]))

            member["donationHistory"][currentSeason]["savedDonations"] += member["donationHistory"][currentSeason]["donations"]
            member["donationHistory"][currentSeason]["savedDonationsReceived"] += member["donationHistory"][currentSeason]["donationsReceived"]

        member["donationHistory"][currentSeason]["donations"] = m["donations"]
        member["donationHistory"][currentSeason]["donationsReceived"] = m["donationsReceived"]

        member["donationDisplay"] = m["donations"]
        if member["donationHistory"][currentSeason]["savedDonations"] > 0:
            member["donationDisplay"] = "{} (+{})".format(
                        m["donations"],
                        member["donationHistory"][currentSeason]["savedDonations"])

        member["prevDonationDisplay"] = 0
        if previousSeason in member["donationHistory"]:
            member["prevDonationDisplay"] = member["donationHistory"][previousSeason]["donations"]
            if member["donationHistory"][previousSeason]["savedDonations"] > 0:
                member["prevDonationDisplay"] = "{} (+{})".format(
                            member["donationHistory"][previousSeason]["donations"],
                            member["donationHistory"][previousSeason]["savedDonations"])

        if m["role"] == "leader":
            member["role"] = "L"
        elif m["role"] == "member":
            member["role"] = "M"
        elif m["role"] == "coLeader":
            member["role"] = "CL"
        elif m["role"] == "admin":
            member["role"] = "E"

        if "dateLastIn" not in member:
            member["dateLastIn"] = "-"

        windex=-1
        rank = lastThreeRank = stars = attacks = destruction = missedAttackCounter = 0
        for w in clanManager.storage.getWars():
            if w["state"] == "warEnded":
                windex += 1
                for wm in w["clan"]["members"]:
                    if wm["tag"] == member["tag"]:
                        if "attacks" in wm:
                            member["wars"][windex] = len(wm["attacks"])
                            if windex < clanManager.rankHistory:
                                rank += member["wars"][windex]

                            if len(wm["attacks"]) == 1:
                                wdate = datetime.strptime(w["endTime"], '%Y%m%dT%H%M%S.000Z')
                                if datetime.now() < wdate + timedelta(days=7):
                                    missedAttackCounter +=1

                                    if missedAttackCounter == 2:
                                        missedAttackCounter = 0
                                        member["warningCount"] += 1

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
                                destruction += int(a["destructionPercentage"])
                                attacks += 1

                                if windex < clanManager.rankHistory:
                                    if wm["mapPosition"] - dMapPosition > -3:
                                        rank += bonus
                                    else:
                                        rank += bonus * 0.75

                        else:
                            member["wars"][windex] = -1

                            wdate = datetime.strptime(w["endTime"], '%Y%m%dT%H%M%S.000Z')
                            if datetime.now() < wdate + timedelta(days=7):
                                member["warningCount"] += 1

                        if windex < 2:
                            lastThreeRank = rank

                        sortOrder += member["wars"][windex]
        member["sort"] =  sortOrder

        if attacks > 0:
            member["averageStars"] = round(stars/attacks,1)
            member["averageDestruction"] = round(destruction/attacks)
        else:
            member["averageStars"] = 0
            member["averageDestruction"] = 0

        if "cwlWarning" in member:
            if len(member["cwlWarning"]) > 0:
                member["cwlWarningPenality"] = 500
            else:
                member["cwlWarningPenality"] = 0

        if "warnings" in member:
            member["warnings"] = expireWarnings(member["name"],member["warnings"],7)
            member["warningCount"] = member["warningCount"] + len(member["warnings"])

        if day > clanManager.warLeagueEndDay and "cwlWarning" in member:
            member["cwlWarning"] = expireWarnings(member["name"],member["cwlWarning"],30)

        donations = donationsReceived = donationMod = cwlRankMod = 0
        if day <= clanManager.warLeagueEndDay or day >= seasonEnd:
            if previousSeason in member["donationHistory"]:
                donationsReceived = member["donationHistory"][previousSeason]["donationsReceived"] + \
                                    member["donationHistory"][previousSeason]["savedDonationsReceived"]
                donations = member["donationHistory"][previousSeason]["donations"] + \
                                    member["donationHistory"][previousSeason]["savedDonations"]
        else:
            donationsReceived = member["donationHistory"][currentSeason]["donationsReceived"] + \
                                member["donationHistory"][currentSeason]["savedDonationsReceived"]
            donations = member["donationHistory"][currentSeason]["donations"] + \
                                member["donationHistory"][currentSeason]["savedDonations"]

        member["donationMod"] = "+" + str(int(donations/100))
        member["cwlRankMod"] = int(donations/2000)
        if member["cwlRankMod"] > 6:
            member["cwlRankMod"] = 6

        member["rank"] = int((donations/100)+(rank*100))
        if "cwlWarningPenality" in member:
            member["rank"] = member["rank"] - member["cwlWarningPenality"]
        else:
            member["cwlWarningPenality"] = 0

        member["lastThreeRank"] = int((donations/100)+(lastThreeRank*100))

        if member["rank"] < 0:
            member["rank"] = 0

        if "warPreference" not in member:
            member["warPreference"] = "out"

        if member["warPreference"] == "out":
            member["rank"] = -1

        members.append(member)

    mytemplate = Template(filename=clanManager.homeTemplate)
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

    st.set_page(mytemplate.render(clan=clanManager.clanDetails,
                             members=members,
                             warlog=clanManager.storage.getWarLog()["items"],
                             warState=clanManager.storage.getWarLog()["currentState"],
                             lastUpdated=st.get_last_updated(),
                             banners=getBanners()
                             ))


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

def pruneBackups():
    path = "data/backup"
    if not os.path.exists(path):
        return
    now = time.time()

    for filename in os.listdir(path):
        filepath = os.path.join(path, filename)
        if os.path.getmtime(filepath) < now - 7 * 86400:
            if os.path.isfile(filepath):
                os.remove(filepath)

def getBanners():
    path = "static/banners"
    banners = []

    for filename in os.listdir(path):
        banners.append(filename)

    return(banners)

def readData():
    if os.path.exists(clanManager.dataFile):
        try:
            with open(clanManager.dataFile) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            app.logger.error("Failed to load data file: %s", e)
            app.logger.warning("Starting with empty state — data file may be corrupt")
            return({})
    else:
        return({})

def readNotes():
    if os.path.exists(clanManager.notesDataFile):
        try:
            with open(clanManager.notesDataFile) as f:
                c = json.load(f)
                return(c["notes"])
        except (json.JSONDecodeError, IOError) as e:
            app.logger.error("Failed to load notes file: %s", e)
            return('hi')
    else:
        return('hi')

def loadContent():
    if os.path.exists(clanManager.homeHeader):
        with open(clanManager.homeHeader) as f:
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
    key = player = toggle = ""
    player = request.form.get('player')
    date = request.form.get('date')
    cwlWarning = request.form.get('type')
    key = request.form.get('key')
    app.logger.debug("Warning form; " + str(request.form.to_dict(flat=False)))

    if hmac.compare_digest(str(key or ''), str(clanManager.notesKey or '')):
        members = state.get_member_list()

        if player != None:
            if date is None:
                if cwlWarning == "y":
                    state.add_cwl_warning(player)
                state.add_warning(player)
            else:
                if cwlWarning == "y":
                    state.remove_cwl_warning(player, date)
                else:
                    state.remove_warning(player, date)

        for m in members:
            form = addWarningForm()
            form.key.data = key
            form.player.data = m["tag"]
            form.type.data = False
            m["form"] = form
            m["performanceWarning"] = False
            warning_forms = []
            for p in clanManager.storage.getMembers():
                if m["tag"] == p["tag"]:
                    if "warnings" in p:
                        for w in p["warnings"]:
                            warningForm = deleteWarningForm()
                            warningForm.key.data = key
                            warningForm.player.data = m["tag"]
                            warningForm.date.data = w
                            warningForm.type.data = False
                            warningForm.submit.label.text = w
                            warning_forms.append(warningForm)

                        if len(warning_forms)>0:
                            m["performanceWarning"] = True

                    if "cwlWarning" in p:
                        for w in p["cwlWarning"]:
                            warningForm = deleteWarningForm()
                            warningForm.key.data = key
                            warningForm.player.data = m["tag"]
                            warningForm.date.data = w
                            warningForm.type.data = "y"
                            warningForm.submit.label.text = "CWL Warning"
                            warning_forms.append(warningForm)

                    m["manualWarnings"] = warning_forms
                    break

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

    if hmac.compare_digest(str(key or ''), str(clanManager.notesKey or '')):
        form.key.data = key

        if post == "" or not post:
            form.post.data = readNotes()
        else:
            form.post.data = post
            state.save_notes(post)

        return render_template(clanManager.notesTemplate,form=form,key=key)

    else:
        return redirect("/", code=302)

@app.route("/clan",methods = ['GET'])
def showData():
    key = request.args.get('key', '')
    if hmac.compare_digest(str(key), str(clanManager.notesKey or '')):
        return jsonify(state.get_clan_snapshot())
    return redirect("/", code=302)

@app.route("/",methods = ['GET'])
def hello():
    return state.get_page()

@app.route("/cwl",methods = ['GET'])
def cwl():
    return state.get_cwl_page()
