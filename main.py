"""Run WFlash from the repo root: `python main.py [--adapter fake|real] [--verbose] [--smoke]`.

Same app as `python -m wflash`; the repo root is put on sys.path so this also works
when the package is not pip-installed or when started from another directory.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wflash.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
