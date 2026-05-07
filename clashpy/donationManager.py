import utils


SEASON_DONATION_FIELDS = ("donations", "donationsReceived", "savedDonations", "savedDonationsReceived")

DONATION_RANK_DIVISOR = 100
DONATION_CWL_RANK_DIVISOR = 2000
CWL_RANK_MOD_MAX = 6


def processDonations(member, apiMember, currentSeason, previousSeason, day, seasonEnd, logger=None):
    member["donationsReceived"] = apiMember["donationsReceived"]
    member["donations"] = apiMember["donations"]

    if "donationHistory" not in member:
        member = utils.addDonationHistory(member, currentSeason, previousSeason)

    if currentSeason not in member["donationHistory"]:
        member["donationHistory"][currentSeason] = _emptySeason()

    if apiMember["donations"] < member["donationHistory"][currentSeason]["donations"] and day != seasonEnd:
        if logger:
            logger.debug("Saving donations for {} - donations: {} saved: +{}".format(
                member["name"],
                apiMember["donations"],
                member["donationHistory"][currentSeason]["donations"]))
        member["donationHistory"][currentSeason]["savedDonations"] += member["donationHistory"][currentSeason]["donations"]
        member["donationHistory"][currentSeason]["savedDonationsReceived"] += member["donationHistory"][currentSeason]["donationsReceived"]

    member["donationHistory"][currentSeason]["donations"] = apiMember["donations"]
    member["donationHistory"][currentSeason]["donationsReceived"] = apiMember["donationsReceived"]

    member["donationDisplay"] = _formatDonationDisplay(
        apiMember["donations"],
        member["donationHistory"][currentSeason]["savedDonations"]
    )

    member["prevDonationDisplay"] = _previousDonationDisplay(member, previousSeason)

    return member


def calculateDonationRank(member, currentSeason, previousSeason, day, warLeagueEndDay, seasonEnd):
    donations = donationsReceived = 0

    if day <= warLeagueEndDay or day >= seasonEnd:
        if previousSeason in member.get("donationHistory", {}):
            prev = member["donationHistory"][previousSeason]
            donationsReceived = prev["donationsReceived"] + prev["savedDonationsReceived"]
            donations = prev["donations"] + prev["savedDonations"]
    else:
        curr = member["donationHistory"][currentSeason]
        donationsReceived = curr["donationsReceived"] + curr["savedDonationsReceived"]
        donations = curr["donations"] + curr["savedDonations"]

    member["donationMod"] = "+" + str(int(donations / DONATION_RANK_DIVISOR))
    member["cwlRankMod"] = min(int(donations / DONATION_CWL_RANK_DIVISOR), CWL_RANK_MOD_MAX)

    return donations, donationsReceived, member


def _formatDonationDisplay(currentDonations, savedDonations):
    # Always returns str for consistent template rendering
    if savedDonations > 0:
        return "{} (+{})".format(currentDonations, savedDonations)
    return str(currentDonations)


def _previousDonationDisplay(member, previousSeason):
    if previousSeason not in member.get("donationHistory", {}):
        return 0

    prev = member["donationHistory"][previousSeason]
    display = prev["donations"]
    if prev.get("savedDonations", 0) > 0:
        display = "{} (+{})".format(prev["donations"], prev["savedDonations"])
    return display


def _emptySeason():
    return {field: 0 for field in SEASON_DONATION_FIELDS}