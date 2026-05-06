import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'clashpy'))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import make_persistance_manager
import pytest


@pytest.fixture
def pm(tmp_path):
    return make_persistance_manager(str(tmp_path))