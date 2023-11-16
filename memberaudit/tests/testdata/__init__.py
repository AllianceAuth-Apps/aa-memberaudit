import inspect
import os

_current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
_FILENAME_EVEUNIVERSE_TESTDATA = "eveuniverse.json"


def eveuniverse_test_data_filename():
    return f"{_current_dir}/{_FILENAME_EVEUNIVERSE_TESTDATA}"
