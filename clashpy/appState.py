import copy
import threading
from datetime import datetime


class AppState:
    def __init__(self, clan_manager, write_json_fn, logger):
        self._lock = threading.RLock()
        self._clan = {}
        self._page = ""
        self._cwl_page = ""
        self._day = int(datetime.now().strftime("%d"))
        self._clan_manager = clan_manager
        self._write_json = write_json_fn
        self._logger = logger

    def init_clan(self, data):
        with self._lock:
            self._clan = data
            self._day = int(datetime.now().strftime("%d"))

    def get_page(self):
        with self._lock:
            return self._page

    def get_cwl_page(self):
        with self._lock:
            return self._cwl_page

    def get_clan_snapshot(self):
        with self._lock:
            return copy.deepcopy(self._clan)

    def get_clan_ref(self):
        """Returns the internal clan dict reference.

        UNSAFE: caller must ensure no concurrent writes (use only at
        startup before the scheduler starts, e.g. for Migration).
        """
        with self._lock:
            return self._clan

    def get_day(self):
        with self._lock:
            return self._day

    def get_member_list(self):
        with self._lock:
            return copy.deepcopy(self._clan.get("clan", {}).get("memberList", []))

    def get_last_updated(self):
        with self._lock:
            return self._clan.get("lastUpdated", "")

    def begin_update(self, api_data):
        """Set day, clan data, and lastUpdated for this update cycle.

        Must be followed by processResults() then finish_update().
        These three steps are intentionally NOT atomic: page and cwlPage
        are updated independently, so a concurrent request may see a new
        lastUpdated with the previous page. This is acceptable because
        the page is always updated within the same scheduler tick.
        """
        with self._lock:
            self._day = int(datetime.now().strftime("%d"))
            self._clan["clan"] = api_data["clan"]
            self._clan["lastUpdated"] = datetime.now().strftime("%c")

    def set_page(self, rendered):
        with self._lock:
            self._page = rendered

    def finish_update(self, rendered_cwl_page):
        with self._lock:
            data = copy.deepcopy(self._clan)
            cwl = rendered_cwl_page
            data_file = self._clan_manager.dataFile

        self._write_json(data_file, data)

        with self._lock:
            if cwl is not None:
                self._cwl_page = cwl

    def add_warning(self, player_tag):
        with self._lock:
            wdate = datetime.now().strftime("%Y%m%dT%H%M")
            self._clan_manager.storage.add_warning(player_tag, wdate)
            self._logger.debug("Add Warning " + player_tag)

    def remove_warning(self, player_tag, date):
        with self._lock:
            self._clan_manager.storage.remove_warning(player_tag, date)
            self._logger.debug("Removing Warning " + player_tag + " " + date)

    def add_cwl_warning(self, player_tag):
        with self._lock:
            wdate = datetime.now().strftime("%Y%m%dT%H%M")
            self._clan_manager.storage.add_cwl_warning(player_tag, wdate)
            self._logger.debug("Add CWL Warning " + player_tag)

    def remove_cwl_warning(self, player_tag, date):
        with self._lock:
            self._clan_manager.storage.remove_cwl_warning(player_tag, date)
            self._logger.debug("Removing CWL Warning " + player_tag + " " + date)

    def save_notes(self, notes_text):
        with self._lock:
            notes_file = self._clan_manager.notesDataFile
            data = {"notes": notes_text}

        self._write_json(notes_file, data)
