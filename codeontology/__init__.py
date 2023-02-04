"""A tool and ontology to model object-oriented programming languages."""

LOGGER = None
RECURSION_LIMIT = 1000


def initialize():
    import logging
    from logging.config import fileConfig
    from pathlib import Path
    import sys

    global LOGGER

    fileConfig(Path(__file__).parent.joinpath("logging.ini"))
    LOGGER = logging.getLogger()
    sys.setrecursionlimit(RECURSION_LIMIT)


initialize()
