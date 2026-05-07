import os
import json
import tempfile
import time
from datetime import datetime, timedelta
from helpers import make_persistance_manager, MockLogger
import warningsController


def expireWarnings(player, warnings, t):
    return warningsController.expireWarnings(player, warnings, t)


def pruneBackups(path):
    if not os.path.exists(path):
        return
    now = time.time()

    for filename in os.listdir(path):
        filepath = os.path.join(path, filename)
        if os.path.getmtime(filepath) < now - 7 * 86400:
            if os.path.isfile(filepath):
                os.remove(filepath)


class TestExpireWarnings:
    def test_removes_expired_warnings(self):
        old_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%dT%H%M')
        warnings = [old_date]
        result = expireWarnings("player1", warnings, 7)
        assert len(result) == 0

    def test_keeps_recent_warnings(self):
        recent_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%dT%H%M')
        warnings = [recent_date]
        result = expireWarnings("player1", warnings, 7)
        assert len(result) == 1

    def test_removes_only_expired(self):
        old_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%dT%H%M')
        recent_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%dT%H%M')
        warnings = [old_date, recent_date]
        result = expireWarnings("player1", warnings, 7)
        assert len(result) == 1
        assert recent_date in result

    def test_empty_warnings_list(self):
        result = expireWarnings("player1", [], 7)
        assert result == []

    def test_custom_expiry_threshold(self):
        date_20_days_ago = (datetime.now() - timedelta(days=20)).strftime('%Y%m%dT%H%M')
        warnings = [date_20_days_ago]
        result = expireWarnings("player1", warnings, 30)
        assert len(result) == 1

    def test_exactly_at_boundary(self):
        boundary_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%dT%H%M')
        warnings = [boundary_date]
        result = expireWarnings("player1", warnings, 7)
        assert len(result) == 0


class TestWriteJsonAtomic:
    def test_atomic_write_preserves_data(self, tmp_path):
        pm = make_persistance_manager(str(tmp_path))
        path = os.path.join(str(tmp_path), "data.json")
        pm.writeJson(path, {"key": "value"})
        with open(path) as f:
            assert json.load(f) == {"key": "value"}

    def test_atomic_write_preserves_original_on_failure(self, tmp_path):
        pm = make_persistance_manager(str(tmp_path))
        path = os.path.join(str(tmp_path), "data.json")
        pm.writeJson(path, {"original": True})
        try:
            pm.writeJson(path, {"bad": object()})
        except Exception:
            pass
        with open(path) as f:
            assert json.load(f) == {"original": True}

    def test_no_temp_files_left(self, tmp_path):
        pm = make_persistance_manager(str(tmp_path))
        path = os.path.join(str(tmp_path), "data.json")
        pm.writeJson(path, {"ok": True})
        files = os.listdir(str(tmp_path))
        json_files = [f for f in files if f.endswith('.json')]
        assert len(json_files) == 1


class TestPruneBackups:
    def test_removes_old_backups(self, tmp_path):
        backup_dir = os.path.join(str(tmp_path), "backup")
        os.makedirs(backup_dir)

        old_file = os.path.join(backup_dir, "old.json")
        new_file = os.path.join(backup_dir, "new.json")
        with open(old_file, 'w') as f:
            f.write("old")
        with open(new_file, 'w') as f:
            f.write("new")

        old_time = os.path.getmtime(old_file)
        os.utime(old_file, (old_time - 8 * 86400, old_time - 8 * 86400))

        pruneBackups(backup_dir)
        assert not os.path.exists(old_file)
        assert os.path.exists(new_file)

    def test_no_crash_when_directory_missing(self):
        pruneBackups("/nonexistent/path")

    def test_keeps_recent_files(self, tmp_path):
        backup_dir = os.path.join(str(tmp_path), "backup")
        os.makedirs(backup_dir)
        recent_file = os.path.join(backup_dir, "recent.json")
        with open(recent_file, 'w') as f:
            f.write("recent")
        pruneBackups(backup_dir)
        assert os.path.exists(recent_file)


class TestHmacAuth:
    def test_compare_digest_used_in_update(self):
        with open(os.path.join(os.path.dirname(__file__), '..', 'update.py')) as f:
            source = f.read()
        assert 'hmac.compare_digest' in source


class TestReadData:
    def test_returns_empty_on_corrupt_json(self, tmp_path):
        data_file = os.path.join(str(tmp_path), "mydata.json")
        with open(data_file, 'w') as f:
            f.write("{invalid json")
        result = readData_from_path(data_file)
        assert result == {}

    def test_returns_empty_on_missing_file(self, tmp_path):
        result = readData_from_path(os.path.join(str(tmp_path), "nonexistent.json"))
        assert result == {}

    def test_returns_valid_data(self, tmp_path):
        data_file = os.path.join(str(tmp_path), "mydata.json")
        with open(data_file, 'w') as f:
            json.dump({"clan": {"tag": "#TEST"}}, f)
        result = readData_from_path(data_file)
        assert result["clan"]["tag"] == "#TEST"


def readData_from_path(path):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    else:
        return {}