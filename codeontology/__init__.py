import logging

import owlready2 as owl

ontology = None
glob_download_path: str = ""


def init():
    import os
    import shutil

    global ontology, glob_download_path

    ontology_path = os.path.join(os.path.abspath(__path__[0]), "codeontology.owl")
    ontology = owl.get_ontology(ontology_path)
    namespace = ontology.load()

    glob_download_path = os.path.normpath(os.path.join(os.path.abspath(__path__[0]), "../../_downloads"))
    if os.path.isdir(glob_download_path):
        shutil.rmtree(glob_download_path)
    os.mkdir(glob_download_path)

    logging.basicConfig(level=logging.WARNING)


init()
