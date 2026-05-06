import os
import json
from helpers import make_persistance_manager, make_ended_war, make_member, MockLogger


class TestPersistanceManagerInit:
    def test_starts_with_empty_wars(self, pm):
        assert pm.getWars() == []

    def test_starts_with_empty_members(self, pm):
        assert pm.getMembers() == []


class TestWriteJson:
    def test_writes_valid_json(self, pm, tmp_path):
        path = os.path.join(str(tmp_path), "test.json")
        pm.writeJson(path, {"key": "value"})
        with open(path) as f:
            assert json.load(f) == {"key": "value"}

    def test_atomic_write_no_partial_on_error(self, pm, tmp_path):
        path = os.path.join(str(tmp_path), "test.json")
        pm.writeJson(path, {"original": True})
        try:
            pm.writeJson(path, {"bad": object()})
        except Exception:
            pass
        with open(path) as f:
            assert json.load(f) == {"original": True}

    def test_creates_parent_directories(self, pm, tmp_path):
        path = os.path.join(str(tmp_path), "sub", "dir", "test.json")
        pm.writeJson(path, {"deep": True})
        with open(path) as f:
            assert json.load(f) == {"deep": True}


class TestAddWar:
    def test_add_first_war(self, pm):
        war = make_ended_war()
        pm.addWar(war)
        assert len(pm.getWars()) == 1
        assert pm.getWars()[0]["preparationStartTime"] == war["preparationStartTime"]

    def test_add_multiple_wars(self, pm):
        war1 = make_ended_war(prep_time="20250101T000000.000Z")
        war2 = make_ended_war(prep_time="20250102T000000.000Z")
        pm.addWar(war1)
        pm.addWar(war2)
        assert len(pm.getWars()) == 2
        assert pm.getWars()[0]["preparationStartTime"] == "20250102T000000.000Z"

    def test_update_existing_war_same_prep_time(self, pm):
        war = make_ended_war(prep_time="20250101T000000.000Z")
        pm.addWar(war)
        updated = make_ended_war(prep_time="20250101T000000.000Z", stars=2)
        pm.addWar(updated)
        assert len(pm.getWars()) == 1
        assert pm.getWars()[0]["clan"]["members"][0]["attacks"][0]["stars"] == 2

    def test_removes_preparation_wars_beyond_index_zero(self, pm):
        ended = make_ended_war(prep_time="20250101T000000.000Z")
        prep = {"state": "preparation", "preparationStartTime": "20250103T000000.000Z", "endTime": "20250104T000000.000Z"}
        pm._wars = [ended, prep]
        pm.addWar(ended)
        preparation_wars = [i for i, w in enumerate(pm.getWars()) if w["state"] == "preparation" and i > 0]
        assert len(preparation_wars) == 0

    def test_converts_inwar_to_warended_beyond_index_zero(self, pm):
        ended = make_ended_war(prep_time="20250101T000000.000Z")
        pm.addWar(ended)
        inwar = {"state": "inWar", "preparationStartTime": "20250102T000000.000Z", "endTime": "20250103T000000.000Z"}
        pm._wars.append(inwar)
        new_ended = make_ended_war(prep_time="20250104T000000.000Z")
        pm.addWar(new_ended)
        for i, w in enumerate(pm.getWars()):
            if i > 0:
                assert w["state"] == "warEnded"

    def test_trims_to_rank_history(self, pm):
        pm._clanManager.rankHistory = 3
        for i in range(5):
            war = make_ended_war(prep_time=f"2025010{i+1}T000000.000Z")
            pm.addWar(war)
        assert len(pm.getWars()) <= 3


class TestUpdateMembers:
    def test_add_new_member(self, pm):
        member = make_member()
        pm.updateMembers([member])
        assert len(pm.getMembers()) == 1
        assert pm.getMembers()[0]["tag"] == "#P1"

    def test_update_existing_member(self, pm):
        pm.updateMembers([make_member(donations=100)])
        pm.updateMembers([make_member(donations=200)])
        assert len(pm.getMembers()) == 1
        assert pm.getMembers()[0]["donations"] == 200

    def test_get_members_returns_copy(self, pm):
        pm.updateMembers([make_member()])
        members = pm.getMembers()
        members.append({"tag": "#FAKE"})
        assert len(pm.getMembers()) == 1

    def test_get_member_by_tag(self, pm):
        pm.updateMembers([make_member(tag="#ABC")])
        m = pm.getMember("#ABC")
        assert m["tag"] == "#ABC"

    def test_get_member_returns_copy(self, pm):
        pm.updateMembers([make_member(tag="#ABC")])
        pm.add_warning("#ABC", "20250101T1200")
        m = pm.getMember("#ABC")
        m["name"] = "MUTATED"
        m["warnings"].append("FAKE")
        original = pm.getMember("#ABC")
        assert original["name"] == "Player1"
        assert len(original["warnings"]) == 1

    def test_get_member_not_found_returns_tag_only(self, pm):
        m = pm.getMember("#MISSING")
        assert m == {"tag": "#MISSING"}

    def test_persists_to_file(self, pm):
        pm.updateMembers([make_member()])
        with open(pm._membersDataFile) as f:
            data = json.load(f)
        assert len(data) == 1


class TestTrimList:
    def test_trims_to_size(self, pm):
        lst = [1, 2, 3, 4, 5]
        result = pm._trimList(lst, 3)
        assert result == [1, 2, 3]

    def test_no_trim_when_already_size(self, pm):
        lst = [1, 2, 3]
        result = pm._trimList(lst, 3)
        assert result == [1, 2, 3]


class TestWarningMethods:
    def test_add_warning(self, pm):
        pm._members = [{"tag": "#P1", "name": "Player1"}]
        pm.add_warning("#P1", "20250101T1200")
        members = pm.getMembers()
        assert members[0]["warnings"] == ["20250101T1200"]
        assert members[0]["warningCount"] == 1

    def test_remove_warning(self, pm):
        pm._members = [{"tag": "#P1", "name": "Player1", "warnings": ["20250101T1200"], "warningCount": 1}]
        pm.remove_warning("#P1", "20250101T1200")
        members = pm.getMembers()
        assert members[0]["warnings"] == []
        assert members[0]["warningCount"] == 0

    def test_add_cwl_warning(self, pm):
        pm._members = [{"tag": "#P1", "name": "Player1"}]
        pm.add_cwl_warning("#P1", "20250101T1200")
        members = pm.getMembers()
        assert members[0]["cwlWarning"] == ["20250101T1200"]

    def test_remove_cwl_warning(self, pm):
        pm._members = [{"tag": "#P1", "name": "Player1", "cwlWarning": ["20250101T1200"]}]
        pm.remove_cwl_warning("#P1", "20250101T1200")
        members = pm.getMembers()
        assert members[0]["cwlWarning"] == []


class TestSortAlphaNum:
    def test_sorts_alphanumerically(self, pm):
        items = ["file10", "file2", "file1"]
        assert pm._sortAlphaNum(items) == ["file1", "file2", "file10"]


class TestLoadMembers:
    def test_handles_corrupt_json(self, pm):
        with open(pm._membersDataFile, 'w') as f:
            f.write("{invalid json")
        pm._loadMembers()
        assert pm.getMembers() == []


class TestLoadWars:
    def test_handles_corrupt_war_file(self, pm, tmp_path):
        corrupt_file = os.path.join(pm._warDataPath, "corrupt.json")
        with open(corrupt_file, 'w') as f:
            f.write("{invalid")
        pm._wars = []
        pm._loadWars()
        assert pm.getWars() == []


class TestWarLog:
    def test_set_and_get_warlog(self, pm):
        warlog = {"items": [{"result": "win"}]}
        pm.setWarLog(warlog)
        assert pm.getWarLog() == warlog


class TestCwlSeason:
    def test_add_cwl_season_creates_files(self, pm, tmp_path):
        league = {"season": "2025-01", "clans": []}
        pm.addCwlSeason("2025-01", league)
        league_path = os.path.join(pm._cwlBasePath, "2025-01", "league.json")
        assert os.path.exists(league_path)

    def test_add_league_round(self, pm, tmp_path):
        league = {"season": "2025-01", "clans": []}
        pm.addCwlSeason("2025-01", league)
        round_data = {"state": "warEnded"}
        pm.addLeagueRound("ABC123", round_data)
        round_path = os.path.join(pm._cwlBasePath, "2025-01", "ABC123.json")
        assert os.path.exists(round_path)