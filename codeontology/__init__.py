"""A tool and ontology to model object-oriented programming languages."""

LOGGER = None


def initialize():
    import logging
    from logging.config import fileConfig
    from pathlib import Path
    global LOGGER

    fileConfig(Path(__file__).parent.joinpath("logging.ini"))
    LOGGER = logging.getLogger()


initialize()
