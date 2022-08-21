import logging
import os
import shutil
from typing import *

import astroid
import owlready2 as owl

from .rdfization.python.explorer.pypi import PyPI

ontology = None
glob_pypi: PyPI
astroid_default_cache = None


def init():
    global ontology, glob_pypi, astroid_default_cache

    ontology_path = os.path.join(os.path.abspath(__path__[0]), "codeontology.owl")
    ontology = owl.get_ontology(ontology_path)
    namespace = ontology.load()

    download_path = os.path.join(os.path.abspath(__path__[0]), "_downloads")
    if os.path.isdir(download_path):
        shutil.rmtree(download_path)
    os.mkdir(download_path)
    glob_pypi = PyPI(download_path)

    astroid_default_cache = astroid.astroid_manager.MANAGER._mod_file_cache.copy()

    # logging.basicConfig(level=logging.WARNING)


init()
