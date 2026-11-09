import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile as _tempfile  # noqa: E402

# GUI tests flash; their history must never land in the developer's real flash_history.csv.
os.environ["WFLASH_HISTORY_FILE"] = os.path.join(_tempfile.mkdtemp(prefix="wflash_test_"), "flash_history.csv")
