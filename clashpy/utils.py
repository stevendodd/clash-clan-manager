import calendar
from datetime import date
from datetime import datetime
import pytz

def getCurrentSeason():
    todays_date = date.today()
    season_month = f'{todays_date.month:02}'
    
    n = int(todays_date.month) + 1
    next_month = f'{n:02}'
    
    month = calendar.monthcalendar(todays_date.year, todays_date.month)
    lastMondayOfMonth = max(month[-1][calendar.MONDAY], month[-2][calendar.MONDAY])

    if todays_date.day > lastMondayOfMonth:
        season_month = next_month 
    
    elif todays_date.day == lastMondayOfMonth and int(datetime.now(pytz.utc).strftime("%H")) >= 5:
        season_month = next_month
        
    return "{}-{}".format(todays_date.year,season_month)


def getPreviousSeason():
    todays_date = date.today()
    
    season_year = todays_date.year    
    last_year = season_year - 1
    
    season_month = f'{todays_date.month:02}'
    n = int(todays_date.month) - 1
    last_month = f'{n:02}'
    if n == 0:
        last_month = '12'    
    
    month = calendar.monthcalendar(todays_date.year, todays_date.month)
    lastMondayOfMonth = max(month[-1][calendar.MONDAY], month[-2][calendar.MONDAY])

    if todays_date.day < lastMondayOfMonth:
        season_month = last_month
        if n == 0:
            season_year = last_year
    
    elif todays_date.day == lastMondayOfMonth and int(datetime.now(pytz.utc).strftime("%H")) < 5:
        season_month = last_month
        if n == 0:
            season_year = last_year
        
    return "{}-{}".format(season_year,season_month)

def getSeasonEndDay():
    todays_date = date.today()
    
    month = calendar.monthcalendar(todays_date.year, todays_date.month)
    return max(month[-1][calendar.MONDAY], month[-2][calendar.MONDAY])


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