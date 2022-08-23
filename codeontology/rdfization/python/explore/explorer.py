import os
from typing import *

from codeontology.rdfization.python import global_pypi
from codeontology.rdfization.python.explore.structure import Project


class Explorer:
    _to_explore_abs_path: str
    _to_explore_project_name: str
    _to_explore_project_version: str = "",
    _recursive: bool
    _max_recursions: int
    _root_download_abs_path: str

    _to_translate: List[Project]

    def __init__(
            self, *,
            to_explore_local_path: str = "",
            to_explore_project_name: str = "",
            to_explore_project_version: str = "",
            recursive: bool = False,
            max_recursions: int = 0,
    ):
        # Check input
        # TODO Improve arguments check without using assertions

        # Only one or the other, not both a local path and a name of a pip project to explore
        if to_explore_local_path:
            to_explore_abs_path = os.path.abspath(to_explore_local_path)
            assert os.path.isdir(to_explore_abs_path), f"{to_explore_abs_path} is not an existing directory"
            assert Project.is_project(to_explore_abs_path), f"{to_explore_abs_path} is not a project path"
            assert not to_explore_project_name
        else:
            assert to_explore_project_name

        # Do not give max_recursions if recursion is not active ...
        if not recursive:
            assert max_recursions == 0
        # ... and do not specify 0 or less recursions if it is active
        else:
            assert max_recursions > 0

        # --- Init ---
        self._to_explore_abs_path = os.path.abspath(to_explore_local_path)
        self._to_explore_project_name = to_explore_project_name
        self._to_explore_project_version = to_explore_project_version
        self._recursive = recursive
        self._max_recursions = max_recursions

        if self._to_explore_project_name:
            abs_projects_path = global_pypi.download_project(
                self._to_explore_project_name,
                self._to_explore_project_version
            )
        else:
            abs_projects_path = os.path.abspath(to_explore_local_path)

        main_project = Project(abs_projects_path, root=True)
        self._to_translate = [main_project]

        if self._recursive:
            done_recursions = 0
            to_expand_project_list = self._to_translate.copy()
            while done_recursions < self._max_recursions and to_expand_project_list:
                new_to_translate = []
                for project in to_expand_project_list:
                    for library in project.dependencies:
                        if library.project:
                            assert isinstance(library.project, Project)
                            assert global_pypi.already_downloaded(library.project.version, library.project.name)
                            new_to_translate.append(library.project)
                            self._to_translate.append(library.project)
                to_expand_project_list = new_to_translate.copy()

    def get_projects(self):
        return self._to_translate
