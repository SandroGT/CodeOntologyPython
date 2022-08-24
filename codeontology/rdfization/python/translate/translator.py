from __future__ import annotations
import os
from typing import List, Dict

import astroid

from codeontology.rdfization.python.explore.structure import Project, Library, Package
from codeontology.rdfization.python.translate.visitor import Visitor


backup_astroid_cache = astroid.astroid_manager.MANAGER.astroid_cache.copy()


class Translator:

    def __init__(self, project: Project):
        assert isinstance(project, Project) and Project.is_project(project.abs_project_path)
        self.translate_project(project)

    def translate_project(self, project: Project):
        from contextlib import contextmanager
        import sys

        @contextmanager
        def root_parsing_environment(project: Project):

            # Add dependencies to sys.path
            c = 0
            for library_set in [project.python, project.libraries, project.dependencies]:
                for library in library_set:
                    search_path = os.path.normpath(os.path.join(library.abs_path, ".."))
                    print(f"{library.abs_path} ---> {search_path}")
                    if search_path not in sys.path:
                        sys.path.insert(0, search_path)
                        c += 1

            try:
                yield

            finally:
                # Remove dependencies from sys.path
                sys.path = sys.path[c:]
                # Restore caches
                astroid.astroid_manager.MANAGER.astroid_cache = backup_astroid_cache.copy()

        with root_parsing_environment(project):
            for package in project.get_packages():
                self.extract_package_rdfs(package)

    def extract_package_rdfs(self, package: Package):
        vst = Visitor(package)
