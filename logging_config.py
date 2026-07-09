import logging
import os
from logging.handlers import RotatingFileHandler

from settings import settings

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Configure root logging: readable console output + a rotating file.

    Call once, as early as possible in process startup. Log files live in
    ``settings.log_dir`` (gitignored) and rotate by size.
    """
    os.makedirs(settings.log_dir, exist_ok=True)
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        settings.log_file_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()  # replace any default/basicConfig handlers
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Keep chatty third-party loggers from drowning our own output
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)  # we log migrations ourselves
