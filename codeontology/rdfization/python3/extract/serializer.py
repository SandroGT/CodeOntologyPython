"""Class and methods to start the RDF serialization from a class representation of a Python3 project."""

from __future__ import annotations

from contextlib import contextmanager
import sys
from typing import Set

import astroid

from codeontology import LOGGER
from codeontology.rdfization.python3.explore import Project, Package
from codeontology.rdfization.python3.extract.parser import Parser
from codeontology.rdfization.python3.extract.transformer import Transformer
from codeontology.rdfization.python3.extract.extractor import Extractor


class Serializer:
    """The main class used to get the RDF triples from a Python3 project.

    The `Serializer` accesses all the information about the Python3 project through the `Project` object, then parses
     the needed and available source code to get the RDF triples related to the project.

    Attributes:
        project (Project): an object representation of the Python3 project from which to extract the triples.
        packages (Set[Package]): the set of packages on which to run the extraction.

    """
    project: Project
    packages: Set[Package]

    def __init__(self, project: Project):
        """Initialize and starts the serialization into RDF triples.

        Args:
            project (Project): an object representation of the Python3 project from which to get the triples.

        """
        self.project = project
        self.packages = set()
        with self.__parsing_environment():
            self.__build_unique_model()
            self.__serialize_from_project()

    @contextmanager
    def __parsing_environment(self):
        """Sets up a valid environment for the source code parsing operations.

        Notes:
            It is not possible to extract all the RDF triples without being able to link the 'abstract syntax tree'
             representations of single modules to each other. For example, a class <C> defined in <module 1> could be
             used in <module 2> after being imported: the class <C> in <module 2> should be recognised as the same
             class defined in <module 1>, and should be possible to retrieve its definition by tracing the imports.
            The parsing library 'astroid' that is used in this project is actually capable of this, by simulating what
             the interpreter would do at runtime to import a name: search it through 'sys.path'! Since the distribution
             packages of a third party library are not added to 'sys.path' until a proper installation is run, and
             since we don't want to install all the dependencies of the project of interest just to extract its RDF
             triples, we then just fake everything! We temporarily and manually add to 'sys.path' all the paths of the
             packages, dependencies, and even the standard library modules of the Python3 version we chose.
            This function does this: prepares a fake environment in which those names are available for import, even
             though they have not been properly installed, and removes all on exit, leaving everything clean.

        """
        # Executed before the 'with' block.
        # Backup of sys.path and astroid cache.
        saved_sys_path = sys.path.copy()
        saved_astroid_cache = astroid.astroid_manager.MANAGER.astroid_cache.copy()
        # Reset sys.path and add the new dependencies to it. We are removing also the references to the Python3 standard
        #  library of the Python3 we are running on, to replace it with the source code of the version we downloaded.
        sys.path = []
        for search_path in [self.project.python3_path, self.project.packages_paths, self.project.dependencies_paths]:
            sys.path.insert(0, str(search_path))

        try:
            # Pass the execution to the 'with' block. During the execution of the 'with' block all the imports will
            #  be done using the modified 'sys.path'. All the already executed imports are not affected.
            yield

        # Executed after the 'with' block.
        finally:
            # Restore sys.path and astroid cache.
            sys.path = saved_sys_path.copy()
            astroid.astroid_manager.MANAGER.astroid_cache = saved_astroid_cache.copy()

    def __build_unique_model(self):
        """Parse the Python modules of interest available in the `Project`, creating their ASTs and adding them to the
         parser caches, so that they can be linked to each other forming some kind of a graph. Apply the proper
         transformation to the parsed packages to integrate useful information.

        Notes:
            This step is used to force the parsing library 'astroid' to store the ASTs in its internal caches. When
             asking 'astroid' to parse some code (a string), it is possible to give additional parameters such as the
             path to the file the source code is coming from, and the name of such module. The name of the module is
             used to store the AST in 'astroid' internal caches, so that it can be retrieved if the same module is
             referenced, for example, in an import statement. What makes this step necessary is that this seems to work
             only in one way: parsing a module for the first time and then tracing it through an import brings to
             retrieve the same AST; tracing it through an import and then parsing it seems to bring to different ASTs
             of the same code.
            So, we first parse all the files at hand, then, and just then, extract the triples!

        """
        LOGGER.info(f"Building unique model of '{self.project.name}':")
        LOGGER.info(f" - parsing project packages and actual referenced dependencies (gets progressively faster);")
        parser = Parser(self.project)
        self.packages = set(parser.parsed_packages.values())
        LOGGER.info(f" - applying transformations to the ASTs of the project and its actual referenced dependencies.")
        Transformer(self.packages)

    def __serialize_from_project(self):
        """Extract the RDF triples."""
        LOGGER.info(f"Extracting RDF triples from '{self.project.name}' (project and actual referenced dependencies).")
        Extractor(self.project)
