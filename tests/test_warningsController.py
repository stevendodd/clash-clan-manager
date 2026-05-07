from datetime import datetime, timedelta
from helpers import make_ended_war, make_member
import warningsController


class TestExpireWarnings:
    def test_removes_expired_warnings(self):
        old_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%dT%H%M')
        warnings = [old_date]
        result = warningsController.expireWarnings("player1", warnings, 7)
        assert len(result) == 0

    def test_keeps_recent_warnings(self):
        recent_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%dT%H%M')
        warnings = [recent_date]
        result = warningsController.expireWarnings("player1", warnings, 7)
        assert len(result) == 1

    def test_removes_only_expired(self):
        old_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%dT%H%M')
        recent_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%dT%H%M')
        warnings = [old_date, recent_date]
        result = warningsController.expireWarnings("player1", warnings, 7)
        assert len(result) == 1
        assert recent_date in result

    def test_empty_warnings_list(self):
        result = warningsController.expireWarnings("player1", [], 7)
        assert result == []

    def test_custom_expiry_threshold(self):
        date_20_days_ago = (datetime.now() - timedelta(days=20)).strftime('%Y%m%dT%H%M')
        warnings = [date_20_days_ago]
        result = warningsController.expireWarnings("player1", warnings, 30)
        assert len(result) == 1

    def test_exactly_at_boundary(self):
        boundary_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%dT%H%M')
        warnings = [boundary_date]
        result = warningsController.expireWarnings("player1", warnings, 7)
        assert len(result) == 0

    def test_multiple_expired(self):
        old1 = (datetime.now() - timedelta(days=10)).strftime('%Y%m%dT%H%M')
        old2 = (datetime.now() - timedelta(days=15)).strftime('%Y%m%dT%H%M')
        recent = (datetime.now() - timedelta(days=3)).strftime('%Y%m%dT%H%M')
        warnings = [old1, old2, recent]
        result = warningsController.expireWarnings("player1", warnings, 7)
        assert len(result) == 1
        assert recent in result


class TestProcessCwlWarnings:
    def test_sets_penalty_when_cwl_warning_exists(self):
        member = {"tag": "#P1", "name": "Player1", "cwlWarning": ["20250101T1200"]}
        result = warningsController.processCwlWarnings(member, 15, 10)
        assert result["cwlWarningPenality"] == 500

    def test_no_penalty_when_cwl_warning_empty(self):
        member = {"tag": "#P1", "name": "Player1", "cwlWarning": []}
        result = warningsController.processCwlWarnings(member, 15, 10)
        assert result["cwlWarningPenality"] == 0

    def test_no_penalty_when_no_cwl_warning_key(self):
        member = {"tag": "#P1", "name": "Player1"}
        result = warningsController.processCwlWarnings(member, 15, 10)
        assert "cwlWarningPenality" not in result

    def test_expires_cwl_warnings_after_war_league(self):
        old_date = (datetime.now() - timedelta(days=35)).strftime('%Y%m%dT%H%M')
        member = {"tag": "#P1", "name": "Player1", "cwlWarning": [old_date]}
        result = warningsController.processCwlWarnings(member, 15, 10)
        assert len(result["cwlWarning"]) == 0

    def test_does_not_expire_cwl_warnings_during_war_league(self):
        recent_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%dT%H%M')
        member = {"tag": "#P1", "name": "Player1", "cwlWarning": [recent_date]}
        result = warningsController.processCwlWarnings(member, 5, 10)
        assert len(result["cwlWarning"]) == 1

    def test_does_not_expire_cwl_before_league_end_day(self):
        old_date = (datetime.now() - timedelta(days=35)).strftime('%Y%m%dT%H%M')
        member = {"tag": "#P1", "name": "Player1", "cwlWarning": [old_date]}
        result = warningsController.processCwlWarnings(member, 8, 10)
        assert len(result["cwlWarning"]) == 1


class TestProcessManualWarnings:
    def test_expires_and_counts_warnings(self):
        recent_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%dT%H%M')
        old_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%dT%H%M')
        member = {"tag": "#P1", "name": "Player1", "warnings": [recent_date, old_date]}
        result = warningsController.processManualWarnings(member, 2)
        assert len(result["warnings"]) == 1
        assert result["warningCount"] == 2 + 1

    def test_no_warnings_key(self):
        member = {"tag": "#P1", "name": "Player1"}
        result = warningsController.processManualWarnings(member, 0)
        assert "warnings" not in result

    def test_adds_warning_count_to_len(self):
        recent_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%dT%H%M')
        member = {"tag": "#P1", "name": "Player1", "warnings": [recent_date]}
        result = warningsController.processManualWarnings(member, 3)
        assert result["warningCount"] == 4


class TestCountMissedAttackWarning:
    def test_no_wars(self):
        assert warningsController.countMissedAttackWarning([], "#P1") == 0

    def test_one_attack_no_warning(self):
        war = make_ended_war(tag="#P1")
        count = warningsController.countMissedAttackWarning([war], "#P1")
        assert count == 0

    def test_missed_attack_gives_warning(self):
        war = {
            "state": "warEnded",
            "endTime": (datetime.now() + timedelta(days=1)).strftime('%Y%m%dT%H%M%S.000Z'),
            "clan": {"tag": "#CLAN1", "members": [{"tag": "#P1", "townhallLevel": 15, "mapPosition": 1}]},
            "opponent": {"members": [{"tag": "#OPP1", "townhallLevel": 15, "mapPosition": 1}]}
        }
        count = warningsController.countMissedAttackWarning([war], "#P1")
        assert count == 1

    def test_two_single_attacks_gives_warning(self):
        now = datetime.now()
        end = (now + timedelta(days=1)).strftime('%Y%m%dT%H%M%S.000Z')
        war1 = {
            "state": "warEnded",
            "endTime": end,
            "clan": {"tag": "#CLAN1", "members": [
                {"tag": "#P1", "townhallLevel": 15, "mapPosition": 1,
                 "attacks": [{"defenderTag": "#OPP1", "stars": 1, "destructionPercentage": 50}]}
            ]},
            "opponent": {"members": [{"tag": "#OPP1", "townhallLevel": 15, "mapPosition": 1}]}
        }
        war2 = {
            "state": "warEnded",
            "endTime": end,
            "clan": {"tag": "#CLAN1", "members": [
                {"tag": "#P1", "townhallLevel": 15, "mapPosition": 1,
                 "attacks": [{"defenderTag": "#OPP1", "stars": 2, "destructionPercentage": 70}]}
            ]},
            "opponent": {"members": [{"tag": "#OPP1", "townhallLevel": 15, "mapPosition": 1}]}
        }
        count = warningsController.countMissedAttackWarning([war1, war2], "#P1")
        assert count == 1

    def test_old_missed_attack_no_warning(self):
        old_end = (datetime.now() - timedelta(days=8)).strftime('%Y%m%dT%H%M%S.000Z')
        war = {
            "state": "warEnded",
            "endTime": old_end,
            "clan": {"tag": "#CLAN1", "members": [{"tag": "#P1", "townhallLevel": 15, "mapPosition": 1}]},
            "opponent": {"members": [{"tag": "#OPP1", "townhallLevel": 15, "mapPosition": 1}]}
        }
        count = warningsController.countMissedAttackWarning([war], "#P1")
        assert count == 0

    def test_player_not_in_war(self):
        war = make_ended_war(tag="#OTHER")
        count = warningsController.countMissedAttackWarning([war], "#P1")
        assert count == 0

    def test_two_attacks_no_warning(self):
        now = datetime.now()
        end = (now + timedelta(days=1)).strftime('%Y%m%dT%H%M%S.000Z')
        war = {
            "state": "warEnded",
            "endTime": end,
            "clan": {"tag": "#CLAN1", "members": [
                {"tag": "#P1", "townhallLevel": 15, "mapPosition": 1,
                 "attacks": [
                     {"defenderTag": "#OPP1", "stars": 3, "destructionPercentage": 100},
                     {"defenderTag": "#OPP2", "stars": 2, "destructionPercentage": 80}
                 ]}
            ]},
            "opponent": {"members": [
                {"tag": "#OPP1", "townhallLevel": 15, "mapPosition": 1},
                {"tag": "#OPP2", "townhallLevel": 14, "mapPosition": 2}
            ]}
        }
        count = warningsController.countMissedAttackWarning([war], "#P1")
        assert count == 0

    def test_in_progress_war_skipped(self):
        war = {
            "state": "inWar",
            "endTime": (datetime.now() + timedelta(days=1)).strftime('%Y%m%dT%H%M%S.000Z'),
            "clan": {"tag": "#CLAN1", "members": [{"tag": "#P1", "townhallLevel": 15, "mapPosition": 1}]},
            "opponent": {"members": [{"tag": "#OPP1", "townhallLevel": 15, "mapPosition": 1}]}
        }
        count = warningsController.countMissedAttackWarning([war], "#P1")
        assert count == 0