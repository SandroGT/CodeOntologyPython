from codeontology import *
from codeontology.rdfization.python.explorer.structure import Project, Library, Package
from codeontology.rdfization.python.explorer.pypi import PyPI


class Explorer:
    __to_explore_abs_path: str
    __to_explore_project_name: str
    __to_explore_project_version: str = "",
    __recursive: bool
    __max_recursions: int
    __root_download_abs_path: str

    __results: list
    __to_explore_abs_path_queue: list[(str, int)]
    __to_translate: List[Union[Project, Library]]

    def __init__(
            self, /,
            to_explore_local_path: str = "",
            to_explore_project_name: str = "",
            to_explore_project_version: str = "",
            recursive: bool = False,
            max_recursions: int = 0,
            root_download_path: str = os.path.normpath("./_downloads")
    ):
        # --- Check arguments ---
        # TODO Improve arguments check without using assertions

        # Only one or the other, not both a local path and a name of a pip project to explore
        if to_explore_local_path:
            assert os.path.isdir(root_download_path)
            assert not to_explore_project_name
        else:
            assert to_explore_project_name

        # Do not give max_recursions if recursion is not active ...
        if not recursive:
            assert max_recursions == 0
        # ... and do not specify 0 or less recursions if it is active
        else:
            assert max_recursions > 0

        # Somewhere we must download, and must be an already created directory
        assert os.path.isdir(root_download_path)

        # --- Init ---
        self.__to_explore_abs_path = os.path.abspath(to_explore_local_path)
        self.__to_explore_project_name = to_explore_project_name
        self.__to_explore_project_version = to_explore_project_version
        self.__recursive = recursive
        self.__max_recursions = max_recursions
        self.__root_download_abs_path = os.path.abspath(root_download_path)

        if self.__to_explore_project_name:
            abs_projects_paths = [python.explorer.PyPI.download_project(
                self.__to_explore_project_name,
                self.__to_explore_project_version,
                self.__root_download_abs_path
            )]
        else:
            abs_projects_paths = self.__find_projects(self.__to_explore_abs_path)

        # Here I have a list of projects or libraries

        self.__to_translate = []
        for abs_path in abs_projects_paths:
            if Project.is_project(abs_path):
                self.__to_translate.append(Project(abs_path))
            elif Library.is_library(abs_path):
                self.__to_translate.append(Library(abs_path))
            else:
                assert False

        if self.__recursive:
            done_recursions = 0
            to_expand = self.__to_translate
            while done_recursions < self.__max_recursions and to_expand:
                new = []
                for pl in to_expand:
                    for d in pl.get_dependencies():
                        if not is_already_downloaded(d):
                            new.append(
                                PyPI.download_project(d.name)
                            )
                for n in new:
                    self.__to_translate.append(n)
                to_expand = new

    def __find_projects(self, path):
        pass
