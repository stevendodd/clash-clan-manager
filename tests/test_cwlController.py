from helpers import MockLogger
from unittest.mock import MagicMock


class TestCwlProcessCWLPlayer:
    def _get_controller(self):
        import cwlController
        cm = MagicMock()
        cm.storage = MagicMock()
        return cwlController.CwlController(cm, MockLogger())

    def test_player_with_attack(self):
        ctrl = self._get_controller()
        member = {
            "tag": "#P1",
            "name": "Player1",
            "townhallLevel": 15,
            "attacks": [
                {"stars": 3, "destructionPercentage": 100, "defenderTag": "#OPP1"}
            ],
            "bestOpponentAttack": {"stars": 1, "destructionPercentage": 50}
        }
        result = ctrl._processCWLPlayer(0, member, {}, "TestClan")
        assert result["tag"] == "#P1"
        assert result["rounds"]["0"]["starsAttack"] == 3
        assert result["rounds"]["0"]["starsDefense"] == 1
        assert result["roundsIn"] == 1

    def test_player_without_attack(self):
        ctrl = self._get_controller()
        member = {
            "tag": "#P2",
            "name": "Player2",
            "townhallLevel": 14
        }
        result = ctrl._processCWLPlayer(0, member, {}, "TestClan")
        assert result["rounds"]["0"]["starsAttack"] == "-"
        assert result["roundsIn"] == 0

    def test_accumulates_across_rounds(self):
        ctrl = self._get_controller()
        member_r1 = {
            "tag": "#P1", "name": "Player1", "townhallLevel": 15,
            "attacks": [{"stars": 2, "destructionPercentage": 80}]
        }
        player = ctrl._processCWLPlayer(0, member_r1, {}, "TestClan")

        member_r2 = {
            "tag": "#P1", "name": "Player1", "townhallLevel": 15,
            "attacks": [{"stars": 3, "destructionPercentage": 100}]
        }
        player = ctrl._processCWLPlayer(1, member_r2, player, "TestClan")

        assert player["totalAttackStars"] == 5
        assert player["roundsIn"] == 2
        assert "0" in player["rounds"]
        assert "1" in player["rounds"]

    def test_rank_calculation(self):
        ctrl = self._get_controller()
        member = {
            "tag": "#P1", "name": "Player1", "townhallLevel": 15,
            "attacks": [{"stars": 3, "destructionPercentage": 100}],
            "bestOpponentAttack": {"stars": 0, "destructionPercentage": 0}
        }
        result = ctrl._processCWLPlayer(0, member, {}, "TestClan")
        expected_rank = 30 + (3 * 3) - 0 + 1
        assert result["rank"] == expected_rank


class TestCwlSortStars:
    def _get_controller(self):
        import cwlController
        cm = MagicMock()
        cm.storage = MagicMock()
        return cwlController.CwlController(cm, MockLogger())

    def test_sorts_by_stars_then_destruction(self):
        ctrl = self._get_controller()
        clans = [
            {"stars": 10, "destruction": 80},
            {"stars": 20, "destruction": 60},
            {"stars": 20, "destruction": 90},
        ]
        clans.sort(reverse=True, key=ctrl._sortStars)
        assert clans[0]["destruction"] == 90
        assert clans[1]["destruction"] == 60