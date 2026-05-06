import os
from helpers import MockLogger


class TestClanManagerMissingConfig:
    def test_raises_file_not_found_when_config_missing(self, tmp_path):
        import clanManager
        config_path = os.path.join(str(tmp_path), "missing_config.json")
        old_config = clanManager.ClanManager.configFile

        try:
            clanManager.ClanManager.configFile = config_path
            try:
                clanManager.ClanManager(MockLogger())
                assert False, "Should have raised FileNotFoundError"
            except FileNotFoundError as e:
                assert config_path in str(e)
        finally:
            clanManager.ClanManager.configFile = old_config

    def test_raises_runtime_error_on_corrupt_config(self, tmp_path):
        import os
        import clanManager
        config_path = os.path.join(str(tmp_path), "bad_config.json")
        with open(config_path, 'w') as f:
            f.write("{not valid json")

        old_config = clanManager.ClanManager.configFile
        try:
            clanManager.ClanManager.configFile = config_path
            try:
                clanManager.ClanManager(MockLogger())
                assert False, "Should have raised RuntimeError"
            except (RuntimeError, FileNotFoundError):
                pass
        finally:
            clanManager.ClanManager.configFile = old_config


class TestClanManagerDefaultPaths:
    def test_config_file_path(self):
        import clanManager
        assert clanManager.ClanManager.configFile == "data/config.json"

    def test_data_file_path(self):
        import clanManager
        assert clanManager.ClanManager.dataFile == "data/mydata.json"

    def test_rank_history_default(self):
        import clanManager
        assert clanManager.ClanManager.rankHistory == 10

    def test_war_league_end_day_default(self):
        import clanManager
        assert clanManager.ClanManager.warLeagueEndDay == 10