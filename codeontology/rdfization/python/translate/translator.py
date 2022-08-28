from __future__ import annotations
from contextlib import contextmanager
import os
import sys
import time
from tqdm import tqdm
from typing import List

import astroid

from codeontology.rdfization.python.explore.structure import Project, Library
from codeontology.rdfization.python.translate.visitor import Visitor


class Translator:
    project: Project

    def __init__(self, project: Project):
        assert isinstance(project, Project) and Project.is_project(project.abs_project_path)
        self.project = project
        # Start parsing and creating rdf triples
        with self.parsing_environment():
            self._build_meta_model()
            self._translate_project()

    @contextmanager
    def parsing_environment(self):
        # Backup of sys.path and astroid cache
        saved_sys_path = sys.path.copy()
        saved_astroid_cache = astroid.astroid_manager.MANAGER.astroid_cache.copy()

        # Reset sys.path and add the new dependencies to it, clear astroid cache
        sys.path = []
        for library_set in [self.project.python, self.project.libraries, self.project.dependencies]:
            for library in library_set:
                search_path = os.path.normpath(os.path.join(library.abs_path, ".."))
                if search_path not in sys.path:
                    sys.path.insert(0, search_path)
        # for key in list(astroid.astroid_manager.MANAGER.astroid_cache.keys()):
        #     del astroid.astroid_manager.MANAGER.astroid_cache[key]

        try:
            yield

        finally:
            # Restore sys.path and astroid cache
            sys.path = saved_sys_path.copy()
            astroid.astroid_manager.MANAGER.astroid_cache = saved_astroid_cache.copy()

    def _build_meta_model(self):
        print(f"Building meta-model of '{self.project.individual.hasName}'")
        for library in self.project.libraries:
            assert isinstance(library, Library)
            packages_list = list(library.root_package.get_packages())
            time.sleep(0.1)
            for package in tqdm(packages_list):
                Visitor.parse(package)
            time.sleep(0.1)

    def _translate_project(self):
        print(f"Extracting RDF triples from '{self.project.individual.hasName}'")
        for library in self.project.libraries:
            assert isinstance(library, Library)
            packages_list = list(library.root_package.get_packages())
            time.sleep(0.1)
            for package in tqdm(packages_list):
                assert getattr(package, "ast", None)
                Visitor.visit_to_extract(package.ast)
            time.sleep(0.1)
