import atexit
import os
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
TMP_DIR = ROOT_DIR / ".tmp" / "pytest"


def _ensure_temp_sqlite_url() -> None:
    if os.getenv("DATABASE_URL"):
        os.environ.setdefault("TEST_DB_URL", os.environ["DATABASE_URL"])
        return

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    fd, db_path = tempfile.mkstemp(prefix="pytest-", suffix=".sqlite3", dir=TMP_DIR)
    os.close(fd)
    os.unlink(db_path)

    database_url = f"sqlite:///{db_path}"
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("TEST_DB_URL", database_url)

    def _cleanup() -> None:
        try:
            os.remove(db_path)
        except FileNotFoundError:
            pass

    atexit.register(_cleanup)


_ensure_temp_sqlite_url()
