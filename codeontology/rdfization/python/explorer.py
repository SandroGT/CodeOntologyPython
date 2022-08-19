import os
import shutil

import codeontology


class Explorer:
    __explore_local_path: str
    __explore_project_name: str
    __recursive: bool
    __max_recursions: int
    __root_download_path: str
    __dependencies_dir: str

    __results: list

    def __init__(
            self, /,
            explore_local_path: str = "",
            explore_project_name: str = "",
            recursive: bool = False,
            max_recursions: int = 0,
            root_download_path: str = os.path.normpath("./_downloads"),
            dependencies_dir: str = "dependencies",
    ):
        # --- Check arguments ---
        # TODO Improve arguments check without using assertions

        # Only one or the other, not both a local path and a name of a pip project to explore
        if explore_local_path:
            assert os.path.isdir(root_download_path)
            assert not explore_project_name
        else:
            assert explore_project_name

        # Do not give max_recursions if recursion is not active ...
        if not recursive:
            assert max_recursions == 0
        # ... and do not specify 0 or less recursions if it is active
        else:
            assert max_recursions > 0

        # Somewhere we must download, and must be an already created directory
        assert os.path.isdir(root_download_path)
        # Somewhere we must put the dependencies inside a project folder
        assert dependencies_dir

        # --- Init ---
        self.__explore_local_path = explore_local_path
        self.__explore_project_name = explore_project_name
        self.__recursive = recursive
        self.__max_recursions = max_recursions
        self.__root_download_path = root_download_path
        self.__dependencies_dir = dependencies_dir
        self.__explore()

    def __explore(self):
        if self.__explore_project_name:
            self.__download_pip_project(self.__explore_project_name, self.__root_download_path)
            self.__explore_local_path =

        self.__explore_path(self.__explore_local_path)

    def __explore_path(self, path: str):
        pass

    @staticmethod
    def __download_pip_project(project_name,
                               abs_download_dir,
                               project_version: str = "") -> str:
        import subprocess
        import sys
        import tarfile

        # SEE https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program
        if project_version:
            download_target = f"{project_name}=={project_version}"
        else:
            download_target = project_name

        # Create a temporary directory in which to download the source archive
        assert os.path.isdir(abs_download_dir)
        abs_temp_path = os.path.join(abs_download_dir, "temp")
        assert not os.path.isdir(abs_temp_path)
        os.mkdir(abs_temp_path)

        # Download only the project source archive
        subprocess.check_call(
            [sys.executable,
             "-m", "pip",
             "download", download_target,
             "-d", abs_temp_path,
             "--no-deps",             # no dependencies
             "--no-binary", ":all:"]  # no distributions, source code
        )

        # Find the downloaded source archive
        assert len(os.listdir(abs_temp_path)) == 1
        abs_archive_path = os.path.join(abs_temp_path, os.listdir(abs_temp_path)[0])

        # Open the archive, extract its content in the temporary directory, then delete it
        with tarfile.open(abs_archive_path) as f_archive:
            f_archive.extractall(abs_temp_path)
        os.remove(abs_archive_path)

        # Move the extracted project folder to the download directory
        assert len(os.listdir(abs_temp_path)) == 1
        project_folder = os.listdir(abs_temp_path)[0]
        project_path = shutil.move(os.path.join(abs_temp_path, project_folder), abs_download_dir)
        assert os.path.isdir(project_path) and project_path == os.path.abspath(project_path)

        # Delete the temporary directory
        shutil.rmtree(abs_temp_path)

        # Return the project folder path
        return project_path


def explore_library(path: str, recursive: bool, max_recursions: int) -> list[
    codeontology.rdfization.python.explorer.Project]:
    """
    This function takes a local path with Python code, or a name of a project that can be
     downloaded through "pypi.org", and explore them to identify all their packages and source
     files and packages. Returns some kind of collection with the results of the search.

    If recursive proceeds to explore the dependencies of the projects too, but for a max number of
     times if we want.
    """
    pass


def explore_pip_library(pip_name: str):
    pass


def download_pip_library(lib_name: str, download_dir: str):
    assert os.path.isdir(download_dir)
    pass


class Project:
    name: str
    has_libraries: list[codeontology.rdfization.python.explorer.Library]
    has_dependencies: list[codeontology.rdfization.python.explorer.Library]
    has_build_file: str  # path

    def __init__(self, path, build_file_path):
        """
        Search for build file, get dependencies and project name
        """
        assert self.is_project(path)
        pass

    @staticmethod
    def is_project(path) -> bool:
        """
        Tells if a directory is a project directory
        """
        pass


class Library:
    name: str
    has_project: codeontology.rdfization.python.explorer.Project
    has_root_package: (str, str)  # `(name, path)`
    has_source_dir: str  # redundant with above maybe
