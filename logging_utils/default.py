import logging
import sys
from typing import Callable


class FunctionHandler(logging.Handler):
    """
    A logging handler that calls a function with the log record.
    """

    def __init__(self, callback_function):
        super().__init__()
        self.callback_function = callback_function

    def emit(self, record):
        formatted_message = self.format(record)
        self.callback_function(formatted_message)


LOGGER = logging.getLogger()


def setup_basic_logging():
    # Set up logger with custom handler
    LOGGER.setLevel(logging.INFO)

    # Also add console handler for visibility
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d:%(funcName)s] %(message)s"
        )
    )

    LOGGER.addHandler(console_handler)
    return LOGGER


def with_logging_function(callable: Callable, level: int = logging.INFO):
    function_handler = FunctionHandler(callable)
    function_handler.setLevel(level)
    LOGGER.addHandler(function_handler)
    return LOGGER


setup_basic_logging()
