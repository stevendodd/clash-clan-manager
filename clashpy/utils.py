import os
import calendar
from datetime import date
from datetime import datetime
import pytz

import datetime

def getCurrentSeason():
    today = datetime.date.today()
    start = datetime.date(2025, 11, 3)
    days_since = (today - start).days
    remainder = days_since % 28 if days_since >= 0 else days_since % 28 - 28  # Handle negative for dates before start
    current_date = today - datetime.timedelta(days=remainder)
    return current_date.strftime('%Y-%m-%d')

def getPreviousSeason():
    current_date = datetime.date.fromisoformat(getCurrentSeason())
    previous_date = current_date - datetime.timedelta(days=28)
    return previous_date.strftime('%Y-%m-%d')

def getSeasonEndDay():
    today = datetime.date.today()
    start = datetime.date(2025, 11, 3)
    
    if today < start:
        return start.day
    
    days_since = (today - start).days
    remainder = days_since % 28
    
    if remainder == 0:
        return today.day
    
    days_to_next = 28 - remainder
    next_date = today + datetime.timedelta(days=days_to_next)
    return next_date.day


def addDonationHistory(member,currentSeason,previousSeason):
    if "donationHistory" not in member:
        member["donationHistory"] = {}
        
    if currentSeason not in member["donationHistory"]:
        member["donationHistory"][currentSeason] = {
               "donations": 0,
               "donationsReceived": 0,
               "savedDonations": 0,
               "savedDonationsReceived": 0 
            }
    
    if previousSeason not in member["donationHistory"]:
        member["donationHistory"][previousSeason] = {
               "donations": 0,
               "donationsReceived": 0,
               "savedDonations": 0,
               "savedDonationsReceived": 0 
            }
    
    if "prevDonationsReceived" in member:
        del member["prevDonationsReceived"]
        
    if "prevDonations" in member:
        del member["prevDonations"]
            
    return member

def touch(path):
    basedir = os.path.dirname(path)
    if not os.path.exists(basedir):
        os.makedirs(basedir)
        
    with open(path, 'a'):
        os.utime(path, None)