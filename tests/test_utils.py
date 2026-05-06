import os
import datetime
import utils


class TestGetCurrentSeason:
    def test_returns_string_in_iso_format(self):
        result = utils.getCurrentSeason()
        parsed = datetime.date.fromisoformat(result)
        assert isinstance(parsed, datetime.date)

    def test_season_is_not_in_future(self):
        result = utils.getCurrentSeason()
        parsed = datetime.date.fromisoformat(result)
        assert parsed <= datetime.date.today()


class TestGetPreviousSeason:
    def test_previous_season_is_28_days_before_current(self):
        current = utils.getCurrentSeason()
        previous = utils.getPreviousSeason()
        diff = (datetime.date.fromisoformat(current) - datetime.date.fromisoformat(previous)).days
        assert diff == 28


class TestGetSeasonEndDay:
    def test_returns_int_between_1_and_31(self):
        result = utils.getSeasonEndDay()
        assert 1 <= result <= 31


class TestAddDonationHistory:
    def test_adds_history_keys(self):
        current = utils.getCurrentSeason()
        previous = utils.getPreviousSeason()
        member = {"tag": "#P1"}
        result = utils.addDonationHistory(member, current, previous)
        assert current in result["donationHistory"]
        assert previous in result["donationHistory"]

    def test_preserves_existing_history(self):
        current = utils.getCurrentSeason()
        member = {"tag": "#P1", "donationHistory": {current: {"donations": 100}}}
        result = utils.addDonationHistory(member, current, utils.getPreviousSeason())
        assert result["donationHistory"][current]["donations"] == 100

    def test_removes_prev_donations_fields(self):
        member = {"tag": "#P1", "prevDonations": 50, "prevDonationsReceived": 30}
        result = utils.addDonationHistory(member, utils.getCurrentSeason(), utils.getPreviousSeason())
        assert "prevDonations" not in result
        assert "prevDonationsReceived" not in result


class TestTouch:
    def test_creates_file(self, tmp_path):
        path = os.path.join(str(tmp_path), "newfile.log")
        utils.touch(path)
        assert os.path.exists(path)

    def test_creates_parent_directories(self, tmp_path):
        path = os.path.join(str(tmp_path), "sub", "dir", "file.log")
        utils.touch(path)
        assert os.path.exists(path)

    def test_does_not_truncate_existing_file(self, tmp_path):
        path = os.path.join(str(tmp_path), "existing.log")
        with open(path, 'w') as f:
            f.write("content")
        utils.touch(path)
        with open(path) as f:
            assert f.read() == "content"