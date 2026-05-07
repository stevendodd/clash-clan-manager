from datetime import datetime, timedelta


EXPIRE_WARNING_DAYS = 7
EXPIRE_CWL_WARNING_DAYS = 30


def expireWarnings(player, warnings, days):
    removeDates = []
    for w in warnings:
        wdate = datetime.strptime(w, '%Y%m%dT%H%M')
        if datetime.now() > wdate + timedelta(days=days):
            removeDates.append(w)

    for w in removeDates:
        warnings.remove(w)

    return warnings


def processCwlWarnings(member, day, warLeagueEndDay):
    if "cwlWarning" in member:
        if len(member["cwlWarning"]) > 0:
            member["cwlWarningPenality"] = 500
        else:
            member["cwlWarningPenality"] = 0

    if day > warLeagueEndDay and "cwlWarning" in member:
        member["cwlWarning"] = expireWarnings(
            member["name"], member["cwlWarning"], EXPIRE_CWL_WARNING_DAYS
        )

    return member


def processManualWarnings(member, warningCount):
    if "warnings" in member:
        member["warnings"] = expireWarnings(
            member["name"], member["warnings"], EXPIRE_WARNING_DAYS
        )
        member["warningCount"] = warningCount + len(member["warnings"])

    return member


def countMissedAttackWarning(warData, memberTag):
    missedAttackCounter = 0
    warningCount = 0
    windex = -1

    for w in warData:
        if w["state"] != "warEnded":
            continue
        windex += 1
        for wm in w["clan"]["members"]:
            if wm["tag"] != memberTag:
                continue
            if "attacks" in wm:
                if len(wm["attacks"]) == 1:
                    wdate = datetime.strptime(w["endTime"], '%Y%m%dT%H%M%S.000Z')
                    if datetime.now() < wdate + timedelta(days=7):
                        missedAttackCounter += 1
                        if missedAttackCounter == 2:
                            missedAttackCounter = 0
                            warningCount += 1
            else:
                wdate = datetime.strptime(w["endTime"], '%Y%m%dT%H%M%S.000Z')
                if datetime.now() < wdate + timedelta(days=7):
                    warningCount += 1

    return warningCount