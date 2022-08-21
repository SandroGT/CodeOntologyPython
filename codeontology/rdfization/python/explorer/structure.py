from codeontology import *
from codeontology.rdfization.python import explorer


class Project:
    name: str
    has_libraries: list[explorer.structure.Library]
    has_dependencies: list[explorer.structure.Library]
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
    has_project: explorer.structure.Project
    has_root_package: explorer.structure.Package
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
    has_library: explorer.structure.Library
    has_packages: list[explorer.structure.Package]  # modules are packages too, ontologically speaking
