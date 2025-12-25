import json
import logging
import os
import sqlite3
import traceback


from datetime import datetime


DATA_PATH = os.environ["DB_PATH"]
DB_PATH = os.path.join(DATA_PATH, "error.db")


def _write_to_database(
    reference: str, error_log: str, timestamp: str = None, additional_data: dict = None
):
    if not timestamp:
        timestamp = datetime.now().isoformat()

    print("""Saving error""", timestamp, reference, error_log, additional_data)

    if additional_data:
        additional_data = json.dumps(additional_data)
    else:
        additional_data = ""

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO error (timestamp, action_id, action_data, error_log) VALUES (?, ?, ?, ?);
            """,
            (
                timestamp,
                reference,
                additional_data,
                error_log,
            ),
        )
        return cur.rowcount


class DatabaseExceptionHandler(logging.Handler):
    """
    Custom logging handler that writes exceptions to a database.
    """

    def __init__(self):
        super().__init__(logging.ERROR)

    def emit(self, record):
        """
        Emit a record. If the record contains exception info, write it to database.

        Args:
            record: LogRecord instance
        """
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info

            # Format the traceback
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            tb_string = "".join(tb_lines)

            # Get timestamp and log level
            timestamp = datetime.fromtimestamp(record.created).isoformat()

            # log_level = record.levelname  # 'ERROR', 'CRITICAL', etc.
            # log_level_num = record.levelno  # 40 for ERROR, 50 for CRITICAL, etc.

            # Write to database
            try:
                _write_to_database(str(record.filename), tb_string, timestamp)
            except Exception as e:
                # Fallback: print error if database write fails
                print(f"Failed to write exception to database: {e}")


def with_database_exception_logging():
    from .logging import LOGGER

    # Add the custom database handler
    db_handler = DatabaseExceptionHandler()
    db_handler.setLevel(logging.ERROR)
    LOGGER.addHandler(db_handler)
