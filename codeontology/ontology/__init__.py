"""Ontology related functionalities."""

import owlready2 as owl

ontology: owl.namespace.Ontology
"""Global ontology object.

This object holds the ontology schema (classes, properties, constraints) and stores all the created individuals through
 the constructors and attributes provided by `owlready2` upon loading an ontology.
"""


def __init():
    """Initialization for ontology related objects."""
    from pathlib import Path
    global ontology
    ontology_file_path = Path(__path__[0]).absolute().joinpath("codeontology.owl")
    ontology = owl.get_ontology(str(ontology_file_path)).load()
    ontology.base_iri = r"http://rdf.webofcode.org/woc/"


__init()
