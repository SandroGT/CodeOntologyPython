"""A tool and ontology to model object-oriented programming languages."""

LOGGER = None
RECURSION_LIMIT = 5000
STACK_SIZE = 128*1024*1024


def initialize():
    import logging
    from logging.config import fileConfig
    from pathlib import Path
    import sys
    import threading

    global LOGGER

    fileConfig(Path(__file__).parent.joinpath("logging.ini"))
    LOGGER = logging.getLogger()
    sys.setrecursionlimit(RECURSION_LIMIT)
    threading.stack_size(STACK_SIZE)


initialize()
