from datetime import datetime, timedelta
from helpers import make_persistance_manager, make_member, MockLogger
import donationManager
import utils


class TestProcessDonations:
    def test_adds_donation_history_if_missing(self):
        member = {"tag": "#P1", "name": "Player1"}
        apiMember = make_member(donations=100, donations_received=200)
        currentSeason = "2025-01"
        previousSeason = "2024-12"
        result = donationManager.processDonations(member, apiMember, currentSeason, previousSeason, 15, 28)
        assert "donationHistory" in result
        assert currentSeason in result["donationHistory"]
        assert previousSeason in result["donationHistory"]

    def test_sets_current_donations(self):
        member = {"tag": "#P1", "name": "Player1"}
        apiMember = make_member(donations=100, donations_received=200)
        result = donationManager.processDonations(member, apiMember, "2025-01", "2024-12", 15, 28)
        assert result["donations"] == 100
        assert result["donationsReceived"] == 200
        assert result["donationHistory"]["2025-01"]["donations"] == 100
        assert result["donationHistory"]["2025-01"]["donationsReceived"] == 200

    def test_saves_donations_on_reset(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 500, "donationsReceived": 1000,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        apiMember = make_member(donations=10, donations_received=20)
        result = donationManager.processDonations(member, apiMember, "2025-01", "2024-12", 15, 28)
        assert result["donationHistory"]["2025-01"]["savedDonations"] == 500
        assert result["donationHistory"]["2025-01"]["savedDonationsReceived"] == 1000
        assert result["donationHistory"]["2025-01"]["donations"] == 10
        assert result["donationHistory"]["2025-01"]["donationsReceived"] == 20

    def test_no_save_on_season_end_day(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 500, "donationsReceived": 1000,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        apiMember = make_member(donations=10, donations_received=20)
        result = donationManager.processDonations(member, apiMember, "2025-01", "2024-12", 28, 28)
        assert result["donationHistory"]["2025-01"]["savedDonations"] == 0

    def test_donation_display_without_saved(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 100, "donationsReceived": 200,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        apiMember = make_member(donations=100, donations_received=200)
        result = donationManager.processDonations(member, apiMember, "2025-01", "2024-12", 15, 28)
        assert result["donationDisplay"] == "100"

    def test_donation_display_with_saved(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 500, "donationsReceived": 1000,
                    "savedDonations": 300, "savedDonationsReceived": 500
                }
            }
        }
        apiMember = make_member(donations=100, donations_received=200)
        result = donationManager.processDonations(member, apiMember, "2025-01", "2024-12", 15, 28)
        assert result["donationHistory"]["2025-01"]["savedDonations"] == 800
        assert isinstance(result["donationDisplay"], str)
        assert "800" in result["donationDisplay"]
        assert "+" in result["donationDisplay"]

    def test_prev_donation_display(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 100, "donationsReceived": 200,
                    "savedDonations": 0, "savedDonationsReceived": 0
                },
                "2024-12": {
                    "donations": 400, "donationsReceived": 800,
                    "savedDonations": 200, "savedDonationsReceived": 100
                }
            }
        }
        apiMember = make_member(donations=100, donations_received=200)
        result = donationManager.processDonations(member, apiMember, "2025-01", "2024-12", 15, 28)
        assert "200" in str(result["prevDonationDisplay"])

    def test_prev_donation_display_no_previous(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 100, "donationsReceived": 200,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        apiMember = make_member(donations=100, donations_received=200)
        result = donationManager.processDonations(member, apiMember, "2025-01", "2024-12", 15, 28)
        assert result["prevDonationDisplay"] == 0

    def test_creates_missing_current_season(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2024-12": {
                    "donations": 100, "donationsReceived": 200,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        apiMember = make_member(donations=50, donations_received=80)
        result = donationManager.processDonations(member, apiMember, "2025-01", "2024-12", 15, 28)
        assert result["donationHistory"]["2025-01"]["donations"] == 50


class TestCalculateDonationRank:
    def test_uses_current_season_during_season(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 500, "donationsReceived": 1000,
                    "savedDonations": 200, "savedDonationsReceived": 300
                },
                "2024-12": {
                    "donations": 100, "donationsReceived": 200,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        donations, donationsReceived, result = donationManager.calculateDonationRank(
            member, "2025-01", "2024-12", 15, 10, 28
        )
        assert donations == 700
        assert donationsReceived == 1300
        assert result["donationMod"] == "+7"
        assert result["cwlRankMod"] == 0

    def test_uses_previous_season_before_season_end(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 500, "donationsReceived": 1000,
                    "savedDonations": 200, "savedDonationsReceived": 300
                },
                "2024-12": {
                    "donations": 800, "donationsReceived": 1500,
                    "savedDonations": 100, "savedDonationsReceived": 200
                }
            }
        }
        donations, donationsReceived, result = donationManager.calculateDonationRank(
            member, "2025-01", "2024-12", 5, 10, 28
        )
        assert donations == 900
        assert donationsReceived == 1700

    def test_cwl_rank_mod_capped_at_six(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 20000, "donationsReceived": 15000,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        donations, _, result = donationManager.calculateDonationRank(
            member, "2025-01", "2024-12", 15, 10, 28
        )
        assert result["cwlRankMod"] == 6

    def test_during_war_league_uses_previous(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 5000, "donationsReceived": 3000,
                    "savedDonations": 1000, "savedDonationsReceived": 500
                },
                "2024-12": {
                    "donations": 200, "donationsReceived": 100,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        donations, _, result = donationManager.calculateDonationRank(
            member, "2025-01", "2024-12", 8, 10, 28
        )
        assert donations == 200

    def test_no_previous_season(self):
        member = {
            "tag": "#P1", "name": "Player1",
            "donationHistory": {
                "2025-01": {
                    "donations": 500, "donationsReceived": 1000,
                    "savedDonations": 0, "savedDonationsReceived": 0
                }
            }
        }
        donations, _, result = donationManager.calculateDonationRank(
            member, "2025-01", "2024-12", 5, 10, 28
        )
        assert donations == 0


class TestFormatDonationDisplay:
    def test_without_saved(self):
        assert donationManager._formatDonationDisplay(100, 0) == "100"

    def test_with_saved(self):
        result = donationManager._formatDonationDisplay(100, 50)
        assert "100" in result
        assert "50" in result
        assert "+" in result

    def test_zero_donations(self):
        assert donationManager._formatDonationDisplay(0, 0) == "0"


class TestPreviousDonationDisplay:
    def test_no_previous_season(self):
        member = {"donationHistory": {}}
        assert donationManager._previousDonationDisplay(member, "2024-12") == 0

    def test_previous_season_without_saved(self):
        member = {
            "donationHistory": {
                "2024-12": {
                    "donations": 400, "savedDonations": 0
                }
            }
        }
        assert donationManager._previousDonationDisplay(member, "2024-12") == 400

    def test_previous_season_with_saved(self):
        member = {
            "donationHistory": {
                "2024-12": {
                    "donations": 400, "savedDonations": 200
                }
            }
        }
        result = donationManager._previousDonationDisplay(member, "2024-12")
        assert "200" in str(result)


class TestEmptySeason:
    def test_all_fields_zero(self):
        season = donationManager._emptySeason()
        for field in donationManager.SEASON_DONATION_FIELDS:
            assert season[field] == 0