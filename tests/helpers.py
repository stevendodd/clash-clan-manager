import os
import json
import threading


class MockLogger:
    def debug(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


class MockClanManager:
    rankHistory = 10

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self._logger = MockLogger()


def make_persistance_manager(data_dir):
    import persistanceManager

    class TestablePersistanceManager(persistanceManager.PersistanceManager):
        def __init__(self, clanManager, logger, base_dir):
            self._clanManager = clanManager
            self._logger = logger
            self._lock = threading.Lock()
            self._wars = []
            self._members = []
            self._currentMemberList = []
            self._warLog = {}

            self._apiBasePath = os.path.join(base_dir, "api")
            self._warDataPath = os.path.join(base_dir, "api", "war")
            self._cwlBasePath = os.path.join(base_dir, "api", "cwl") + "/"
            self._membersBasePath = os.path.join(base_dir, "members") + "/"
            self._membersDataFile = os.path.join(base_dir, "members", "members.json")
            self._membersArchive = os.path.join(base_dir, "members", "membersArchive.json")
            self._cwlSeasonPath = None

            for d in [self._warDataPath, self._cwlBasePath + "tmp", self._membersBasePath]:
                os.makedirs(d, exist_ok=True)

            self._loadWars()
            self._loadMembers()

    cm = MockClanManager(data_dir)
    return TestablePersistanceManager(cm, MockLogger(), data_dir)


def make_ended_war(prep_time="20250101T000000.000Z", end_time="20250102T000000.000Z", tag="#PLAYER1", stars=3, destruction=100):
    return {
        "state": "warEnded",
        "preparationStartTime": prep_time,
        "endTime": end_time,
        "clan": {
            "tag": "#CLAN1",
            "members": [
                {
                    "tag": tag,
                    "townhallLevel": 15,
                    "mapPosition": 1,
                    "attacks": [
                        {
                            "defenderTag": "#OPP1",
                            "stars": stars,
                            "destructionPercentage": destruction,
                        }
                    ]
                }
            ]
        },
        "opponent": {
            "members": [
                {"tag": "#OPP1", "townhallLevel": 15, "mapPosition": 1}
            ]
        }
    }


def make_member(tag="#P1", name="Player1", donations=500, donations_received=1000):
    return {
        "tag": tag,
        "name": name,
        "role": "member",
        "townHallLevel": 15,
        "warPreference": "in",
        "donations": donations,
        "donationsReceived": donations_received,
        "league": {"name": "Legend League"},
        "dateLastSeen": "01 Jan 25",
        "dateLastIn": "01 Jan"
    }