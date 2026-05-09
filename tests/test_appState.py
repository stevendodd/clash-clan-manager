import json
import os
import threading
from datetime import datetime
from helpers import MockLogger


def make_app_state(data_dir):
    import appState
    import persistanceManager

    class TestablePM(persistanceManager.PersistanceManager):
        def __init__(self, clan_manager, logger, base_dir):
            self._clanManager = clan_manager
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
            self._manifestFile = os.path.join(base_dir, "api", "manifest.json")
            self._cwlSeasonPath = None
            for d in [self._warDataPath, self._cwlBasePath + "tmp", self._membersBasePath]:
                if not os.path.exists(d):
                    os.makedirs(d)
            self._migrate()
            self._loadWars()
            self._loadMembers()

    class MockClanManager:
        rankHistory = 10
        warLeagueEndDay = 10
        dataFile = os.path.join(data_dir, "mydata.json")
        backupFile = os.path.join(data_dir, "backup", "mydata_BK.json")
        notesDataFile = os.path.join(data_dir, "notes.json")
        homeHeader = os.path.join(data_dir, "content.html")
        homeTemplate = "templates/home.html"
        cwlTemplate = "templates/cwl.html"
        notesTemplate = "notes.html"
        warningTemplate = "warning.html"
        clanDetails = {"tag": "#TEST", "name": "TestClan", "rankHistory": 10}
        notesKey = "testkey"

        def __init__(self, data_dir):
            self._logger = MockLogger()
            self.storage = TestablePM(self, MockLogger(), data_dir)

    cm = MockClanManager(data_dir)

    def write_json_fn(file, data):
        dir_name = os.path.dirname(file)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
        with open(file, 'w') as f:
            json.dump(data, f)

    return appState.AppState(cm, write_json_fn, MockLogger())


class TestAppStateInit:
    def test_default_values(self, tmp_path):
        s = make_app_state(str(tmp_path))
        assert s.get_page() == ""
        assert s.get_cwl_page() == ""
        assert s.get_last_updated() == ""
        assert s.get_clan_snapshot() == {}
        assert s.get_member_list() == []

    def test_day_is_current(self, tmp_path):
        s = make_app_state(str(tmp_path))
        assert s.get_day() == int(datetime.now().strftime("%d"))


class TestAppStateInitClan:
    def test_init_clan_sets_data(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.init_clan({"clan": {"memberList": [{"tag": "#P1"}]}, "lastUpdated": "now"})
        snap = s.get_clan_snapshot()
        assert snap["clan"]["memberList"][0]["tag"] == "#P1"
        assert snap["lastUpdated"] == "now"

    def test_init_clan_resets_day(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.init_clan({"clan": {"memberList": []}})
        assert s.get_day() == int(datetime.now().strftime("%d"))


class TestAppStateGetMemberList:
    def test_returns_copy(self, tmp_path):
        s = make_app_state(str(tmp_path))
        members = [{"tag": "#P1", "name": "Player1"}]
        s.init_clan({"clan": {"memberList": members}})
        lst = s.get_member_list()
        assert lst == members
        lst.append({"tag": "#P2"})
        assert len(s.get_member_list()) == 1

    def test_deep_copy_isolation(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.init_clan({"clan": {"memberList": [{"tag": "#P1", "name": "Player1"}]}})
        lst = s.get_member_list()
        lst[0]["name"] = "MUTATED"
        original = s.get_member_list()
        assert original[0]["name"] == "Player1"

    def test_empty_when_no_clan(self, tmp_path):
        s = make_app_state(str(tmp_path))
        assert s.get_member_list() == []


class TestAppStateBeginUpdate:
    def test_sets_clan_and_last_updated(self, tmp_path):
        s = make_app_state(str(tmp_path))
        api_data = {"clan": {"tag": "#ABC", "memberList": []}}
        s.begin_update(api_data)
        assert s.get_last_updated() != ""
        assert s.get_clan_snapshot()["clan"]["tag"] == "#ABC"

    def test_updates_day(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.begin_update({"clan": {"memberList": []}})
        assert s.get_day() == int(datetime.now().strftime("%d"))


class TestAppStateSetPage:
    def test_set_and_get_page(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.set_page("<html>Hello</html>")
        assert s.get_page() == "<html>Hello</html>"

    def test_set_and_get_cwl_page(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.finish_update("<cwl>Data</cwl>")
        assert s.get_cwl_page() == "<cwl>Data</cwl>"

    def test_finish_update_none_cwl_page_preserves_previous(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.finish_update("<cwl>First</cwl>")
        assert s.get_cwl_page() == "<cwl>First</cwl>"
        s.finish_update(None)
        assert s.get_cwl_page() == "<cwl>First</cwl>"


class TestAppStateFinishUpdate:
    def test_writes_json_file(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.init_clan({"clan": {"tag": "#X"}, "lastUpdated": "t"})
        s.begin_update({"clan": {"tag": "#Y"}})
        s.finish_update(None)
        cm = s._clan_manager
        assert os.path.exists(cm.dataFile)
        with open(cm.dataFile) as f:
            data = json.load(f)
        assert data["clan"]["tag"] == "#Y"


class TestAppStateSnapshotIsolation:
    def test_snapshot_does_not_mutate_internal(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.init_clan({"clan": {"tag": "#ORIG"}, "lastUpdated": "t"})
        snap = s.get_clan_snapshot()
        snap["clan"]["tag"] = "#MUTATED"
        assert s.get_clan_snapshot()["clan"]["tag"] == "#ORIG"


class TestAppStateClanRef:
    def test_clan_ref_mutations_are_visible(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.init_clan({"clan": {"tag": "#X"}, "lastUpdated": "t"})
        ref = s.get_clan_ref()
        ref["clan"]["tag"] = "#MUTATED"
        assert s.get_clan_ref()["clan"]["tag"] == "#MUTATED"


class TestAppStateWarnings:
    def test_add_warning(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s._clan_manager.storage._members = [{"tag": "#P1", "name": "Player1"}]
        s.add_warning("#P1")
        members = s._clan_manager.storage.getMembers()
        assert "warnings" in members[0]
        assert len(members[0]["warnings"]) == 1

    def test_add_warning_creates_list(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s._clan_manager.storage._members = [{"tag": "#P1", "name": "Player1"}]
        s.add_warning("#P1")
        assert isinstance(s._clan_manager.storage.getMembers()[0]["warnings"], list)

    def test_remove_warning(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s._clan_manager.storage._members = [
            {"tag": "#P1", "name": "Player1", "warnings": ["20250101T1200"]}
        ]
        s.remove_warning("#P1", "20250101T1200")
        members = s._clan_manager.storage.getMembers()
        assert len(members[0]["warnings"]) == 0

    def test_add_cwl_warning(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s._clan_manager.storage._members = [{"tag": "#P1", "name": "Player1"}]
        s.add_cwl_warning("#P1")
        members = s._clan_manager.storage.getMembers()
        assert "cwlWarning" in members[0]
        assert len(members[0]["cwlWarning"]) == 1

    def test_remove_cwl_warning(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s._clan_manager.storage._members = [
            {"tag": "#P1", "name": "Player1", "cwlWarning": ["20250101T1200"]}
        ]
        s.remove_cwl_warning("#P1", "20250101T1200")
        members = s._clan_manager.storage.getMembers()
        assert len(members[0]["cwlWarning"]) == 0


class TestAppStateSaveNotes:
    def test_save_notes_writes_file(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.save_notes("hello world")
        notes_file = s._clan_manager.notesDataFile
        assert os.path.exists(notes_file)
        with open(notes_file) as f:
            data = json.load(f)
        assert data["notes"] == "hello world"


class TestAppStateThreadSafety:
    def test_concurrent_reads_and_writes(self, tmp_path):
        s = make_app_state(str(tmp_path))
        s.init_clan({"clan": {"tag": "#T", "memberList": [{"tag": "#P1", "name": "P1"}]}})
        errors = []

        def writer():
            for i in range(50):
                s.begin_update({"clan": {"tag": "#T{}".format(i), "memberList": []}})
                s.set_page("page{}".format(i))
                s.finish_update(None)

        def reader():
            for _ in range(50):
                try:
                    s.get_clan_snapshot()
                    s.get_page()
                    s.get_day()
                    s.get_member_list()
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader),
                   threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestAppStateDocstrings:
    def test_get_clan_ref_warns_unsafe(self):
        import appState
        assert "UNSAFE" in appState.AppState.get_clan_ref.__doc__

    def test_begin_update_documents_non_atomic(self):
        import appState
        assert "NOT atomic" in appState.AppState.begin_update.__doc__
