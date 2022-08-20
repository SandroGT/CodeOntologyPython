import os
import shutil
from typing import *

from codeontology.rdfization import python


class Explorer:
    __to_explore_abs_path: str
    __to_explore_project_name: str
    __to_explore_project_version: str = "",
    __recursive: bool
    __max_recursions: int
    __root_download_abs_path: str

    __results: list
    __to_explore_abs_path_queue: list[(str, int)]
    __to_translate: List[Union[python.explorer.Project, python.explorer.Library]]

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
            abs_projects_paths = [python.explorer.Pypi.download_project(
                self.__to_explore_project_name,
                self.__to_explore_project_version,
                self.__root_download_abs_path
            )]
        else:
            abs_projects_paths = self.__find_projects(self.__to_explore_abs_path)

        # Here I have a list of projects or libraries

        self.__to_translate = []
        for abs_path in abs_projects_paths:
            if python.explorer.Project.is_project(abs_path):
                self.__to_translate.append(python.explorer.Project(abs_path))
            elif python.explorer.Library.is_library(abs_path):
                self.__to_translate.append(python.explorer.Library(abs_path))
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
                                python.explorer.Pypi.download_project(d.name)
                            )
                for n in new:
                    self.__to_translate.append(n)
                to_expand = new

    def __find_projects(self, path):
        pass
    """
    def __explore(self):
        self.__to_translate = []

        if self.__to_explore_project_name:
            self.__download_pip_project(
                self.__to_explore_project_name,
                self.__to_explore_project_version,
                self.__root_download_abs_path
            )
            to_explore_abs_path = self.__root_download_abs_path
        else:
            to_explore_abs_path = self.__to_explore_abs_path
            
        assert to_explore_abs_path == os.path.abspath(to_explore_abs_path)
        self.__explore_path(to_explore_abs_path, 0)

    def __explore_path(self, abs_path: str, recursions: int = 0):
        if python.explorer.Project.is_project(abs_path):
            # Create project and according to recursion calls explore_path on the dependency folder
            pass
        elif python.explorer.Library.is_library(abs_path):
            # Create project and according to recursion calls explore_path on the dependency folder
            pass
        else:
            for file in os.listdir(abs_path):
                if os.path.isdir(file):
                    self.__explore_path(os.path.join(abs_path, file), recursions)
    """


def explore_library(path: str, recursive: bool, max_recursions: int) -> list[python.explorer.Project]:
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


class Pypi:

    @staticmethod
    def download_python_source(python_version: str):
        pass

    @staticmethod
    def download_project(
            project_name: str,
            project_version: str,
            abs_download_dir: str
    ) -> str:
        import subprocess
        import sys
        import tarfile

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
        # SEE https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program
        process = subprocess.Popen(
            [sys.executable,
             "-m", "pip",
             "download", download_target,
             "-d", abs_temp_path,
             "--no-deps",             # no dependencies
             "--no-binary", ":all:"]  # no distributions, source code
        )
        process.communicate()
        assert process.returncode == 0

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

    @staticmethod
    def get_project_versions(project_name: str):
        import subprocess
        import sys

        process = subprocess.Popen(
            [sys.executable,
             "-m", "pip",
             "index", "versions", project_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, _ = process.communicate()
        assert process.returncode == 0

        out = str(out).split("\\r\\n")[1]
        assert out.startswith("Available versions: ")
        versions = out.split(": ")[1].split(", ")

        return versions


class Project:
    name: str
    has_libraries: list[python.explorer.Library]
    has_dependencies: list[python.explorer.Library]
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
    has_project: python.explorer.Project
    has_root_package: python.explorer.Package
    has_source_dir: str  # redundant with above maybe

    @staticmethod
    def is_library(path) -> bool:
        """
        Tells if a directory is a project directory
        """
        pass


class Package:
    has_path: str
    simple_name: str
    fully_qualified_name: str
    has_library: python.explorer.Library
    has_packages: list[python.explorer.Package]  # modules are packages too, ontologically speaking
