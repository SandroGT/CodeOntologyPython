from __future__ import annotations
import os
from typing import List, Dict

import astroid

from codeontology.rdfization.python.explore.structure import Project, Package
from codeontology.rdfization.python.translate.visitor import Visitor


class Translator:

    _astroid_cache: Dict = None

    def translate_projects(self, projects: List[Project]):
        from contextlib import contextmanager
        import sys

        @contextmanager
        def root_parsing_environment(root_project: Project):
            assert root_project.root

            # Add dependencies to sys.path
            c = 0
            for library in root_project.dependencies:
                sys.path.insert(0, os.path.dirname(library.abs_path))
                c += 1
            sys.path.insert(0, os.path.dirname(root_project.python.abs_path))
            c += 1

            try:
                yield

            finally:
                # Remove dependencies from sys.path
                sys.path = sys.path[c:]

        @contextmanager
        def parsing_environment(root_project: Project, project: Project):
            assert root_project.root and not project.root

            # Add dependencies to sys.path
            c = 0
            for library in project.dependencies:
                sys.path.insert(0, os.path.dirname(library.abs_path))
                c += 1
            sys.path.insert(0, os.path.dirname(root_project.python.abs_path))
            c += 1

            try:
                yield

            finally:
                # Remove dependencies from sys.path
                sys.path = sys.path[c:]
                # Restore astroid caches after root project analysis
                astroid.astroid_manager.MANAGER.astroid_cache = self._astroid_cache.copy()

        root_project = projects[0]
        assert root_project.root
        assert True not in [p.root for p in projects[1:]]

        with root_parsing_environment(root_project):
            for package in root_project.get_packages():
                self.extract_package_rdfs(package)

        self._astroid_cache = astroid.astroid_manager.MANAGER.astroid_cache.copy()

        for project in projects[1:]:
            with parsing_environment(root_project, project):
                for package in project.get_packages():
                    self.extract_package_rdfs(package)

    def extract_package_rdfs(self, package: Package):
        vst = Visitor(package)
        ast = vst.parse(package.abs_path)
        vst.visit_to_extract(ast)
