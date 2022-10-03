"""Class and methods to start the RDF extraction from a class representation of a Python3 project."""

from __future__ import annotations

from contextlib import contextmanager
import sys
from typing import Set

import astroid

from codeontology import logging
from codeontology.ontology import ontology
from codeontology.rdfization.python3.explore import Project, Package
from codeontology.rdfization.python3.extract.parser import parse_source
from codeontology.rdfization.python3.extract.individuals import StructureIndividuals
from codeontology.rdfization.python3.extract.visitor import Visitor


class Extractor:
    """The main class used to extract the triples from a Python3 project.

    The `Extractor` accesses all the information about the Python3 project through the `Project` object, then parses
     the needed and available source code to extract the RDF triples related to the project.

    Attributes:
        project (Project): an object representation of the Python3 project from which to extract the triples.
        packages (Set[Package]): the set of packages on which to run the extraction.

    """
    project: Project
    packages: Set[Package]

    def __init__(self, project: Project):
        """Initialize and starts the extraction of the RDF triples.

        Args:
            project (Project): an object representation of the Python3 project from which to extract the triples.

        """
        self.project = project
        self.packages = set()
        namespace = ontology.load()
        with self.__parsing_environment():
            self.__build_meta_model()
            self.__extract_from_project()

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

    def __build_meta_model(self):
        """Parse all the Python modules available in the `Project`, creating their ASTs and adding them to the parser
         caches, so that they can be linked to each other forming some kind of graph.
        Defines then on which packages we will run the extraction (parsing of some packages could fail).

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
        logging.debug(f"Building meta-model of '{self.project.name}'.")
        # TODO instead of pre-parsing EVERYTHING (that may also fail), parse only the project related packages, but
        #  look at the imports to find which other packages are actually imported. Build a list of packages this way,
        #  then clean the 'astroid' caches and parse again the project packages and the other selected dependency
        #  packages.
        # HACK right now ignoring dependencies, since we are gonna extract only `Class` and `Method` triples directly
        #  from the project, but in the future the outer 'for' will have to iterate over
        #  '(self.project.stdlibs | self.project.dependencies | self.project.libraries)'
        for library in self.project.libraries:
            for package in library.root_package.get_packages():
                parse_source(package)
                if package.ast is not None:
                    self.packages.add(package)

    def __extract_from_project(self):
        """Extract the RDF triples."""
        logging.debug(f"Extracting RDF triples from '{self.project.name}'.")
        StructureIndividuals.extract_structure_individuals(self.project)
        for package in self.project.get_packages():
            if package.ast:
                Visitor.visit_to_extract(package.ast)
