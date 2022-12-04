"""Class representations of the Python3 code structure in the file system."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, Set, Tuple, Union

import astroid

from codeontology import logger
from codeontology.ontology import ontology


class Project:
    """A representation of a Python3 project, modelling both the file system structure of the project (paths to source
     files and folders) and the more conceptual representation as collection of code `Library`es and `Package`s.

    Attributes:
        name (str): the name of the project.
        path (Path): the path to the folder containing the project source.
        packages_path (Path): the path to the folder containing the top level packages paths of the project
         distribution.
        dependencies_path (Path): the path to the folder containing the top level packages paths of the project
         dependencies.
        python3_path (Path): the path to the folder containing the Python3 standard library source code.
        packages (Dict[Path, Package]): a dictionary mapping file `Path`s to their related `Package` in the project.
        libraries (Set[Library]): the set of libraries (top level packages) of the project distribution.
        dependencies (Set[Library]): the set of libraries (top level packages) of the project dependencies.
        stdlibs (Set[Library]): the set of standard libraries in the Python3 specified source.
        # TODO DELETE individual (ontology.Project): the project's individual in the ontology.

    """
    name: str
    path: Path

    packages_paths: Path
    dependencies_paths: Path
    python3_path: Path

    packages: Dict[Path, Package]
    libraries: Set[Library]
    dependencies: Set[Library]
    stdlibs: Set[Library]

    # TODO DELETE individual: ontology.Project

    def __init__(self, project_name: str, project_path: Path, packages_path: Path, dependencies_path: Path,
                 python3_path: Path):
        """Creates a representation of a Python3 project from the files in the file system.

        Args:
            project_name (str): the name of the project.
            project_path (Path): the path to the folder containing the project source.
            packages_path (Path): the path to the folder containing the top level packages paths of the project
             distribution.
            dependencies_path (Path): the path to the folder containing the top level packages paths of the project
             dependencies.
            python3_path (Path): the path to the folder containing the Python3 source.

        Raises:
            Exception: invalid project, distribution or dependency packages.

        """
        project_path = project_path.resolve().absolute()
        packages_path = packages_path.resolve().absolute()
        dependencies_path = dependencies_path.resolve().absolute()
        python3_path = python3_path.resolve().absolute()

        # Check input
        if not Project.is_project(project_path):
            raise Exception(f"Invalid project directory '{project_path}'.")
        for package_path in packages_path.iterdir():
            if not Library.is_library(package_path):
                raise Exception(f"Invalid library '{package_path}'.")
        for dependency_path in dependencies_path.iterdir():
            if not Library.is_library(dependency_path):
                raise Exception(f"Invalid dependency '{dependency_path}'.")
        if not Library.is_library(python3_path):
            raise Exception(f"Invalid standard library '{python3_path}'.")

        # Init
        self.name = project_name
        self.path = project_path
        logger.info(f"Creating object for `Project` '{self.name}' (from '{self.path}').")

        self.packages_paths = packages_path
        self.dependencies_paths = dependencies_path
        self.python3_path = python3_path

        self.packages = dict()

        self.libraries = set()
        for package_path in packages_path.iterdir():
            self.libraries.add(Library(package_path, self))

        self.dependencies = set()
        for dependency_path in dependencies_path.iterdir():
            self.dependencies.add(Library(dependency_path, self))

        self.stdlibs = set()
        for stdlib_path in python3_path.iterdir():
            if Library.is_library(stdlib_path):
                self.stdlibs.add(Library(stdlib_path, self))

        # !!! Thinking about removing this! Many created packages are not actually referenced by the project source
        #  code, and they won't have related triples: so these are not interesting numbers.
        n_libs = len(self.libraries) + len(self.dependencies) + len(self.stdlibs)
        n_pkgs = len([pkg for lib in (self.libraries | self.dependencies | self.stdlibs)
                      for pkg in lib.root_package.get_packages()])
        logger.debug(f"Created '{n_libs:,}' `Library` objects and '{n_pkgs:,}' `Package` objects.")

        # Individual creation is delayed and left for the extraction process.
        # TODO DELETE self.individual = None

    def __hash__(self):
        return self.path.__hash__()

    def __eq__(self, other: Any):
        if type(other) is Project:
            # Leveraging the uniqueness of the file system paths
            return self.path.resolve().absolute() == other.path.resolve().absolute()
        else:
            raise Exception(f"Cannot compare '{type(self)}' with type '{type(other)}'.")

    def __str__(self):
        return str(self.path.resolve().absolute())

    def get_packages(self) -> Iterator[Package]:
        """Get all the packages that are part of the project library.

        Returns:
            Iterator[Package]: an iterator over all the project's libraries packages.

        """
        for library in self.libraries:
            yield from library.root_package.get_packages()

    def find_package(self, path: Path) -> Package:
        """Finds the `Package` related to a file path.

        Args:
            path (Path): path of a file.

        Returns:
            Package: the project `Package` related to that file, or `None` for no matches.

        """
        return self.packages.get(path, None)

    def add_or_replace_stdlib_library(self, path: Path):
        """Adds a new standard library `Library` to the project.

        Args:
            path (Path): the path to the root of the library.

        """
        library_package = self.find_package(path)
        # Remove previous library trace, if it existed
        if library_package:
            for package in library_package.get_packages():
                del self.packages[package.path]
            for stdlib in set(self.stdlibs):
                if stdlib.path == path:
                    self.stdlibs.remove(stdlib)
                    break
        # Add new library
        self.stdlibs.add(Library(path, self))

    @staticmethod
    def is_project(folder_path: Path) -> bool:
        """Determines if a folder defines or not a `Project`.

        Args:
            folder_path (Path): a path to an existing folder.

        Returns:
            bool: `True` if the path points to a valid Project folder, `False` otherwise.

        Raises:
            Exception: nonexistent folder.

        """
        from codeontology.rdfization.python3.utils import ProjectHandler
        return ProjectHandler.is_project_dir(folder_path)


class Library:
    """A representation of a Python3 code library, intended as a top level package/namespace package.

    Attributes:
        name (str): the name of the library.
        path (Path): the path to the file/folder containing the library source.
        project (Project): the project to which the library is related.
        root_package (Package): the top level package defining the library.
        # TODO DELETE individual (ontology.Library): the library's individual in the ontology.

    """
    name: str
    path: Path

    project: Project
    root_package: Package

    # TODO DELETE individual: ontology.Library

    def __init__(self, library_path: Path, project: Project = None):
        """Creates a representation of a Python3 library.

        Args:
            library_path (Path): the path to the file/folder containing the library source.
            project (Project): the project of which the library is part of. May be absent.

        Raises:
            Exception: invalid library.

        """
        library_path = library_path.resolve().absolute()

        # Check input
        if not Library.is_library(library_path):
            raise Exception(f"Invalid library '{library_path}'.")

        # Init
        self.name = Library.__get_name(library_path)
        self.path = library_path

        self.project = project
        self.root_package = Package(library_path, self)

        # Individual creation is delayed and left for the extraction process.
        # TODO DELETE self.individual = None

    def __hash__(self):
        return self.path.__hash__()

    def __eq__(self, other):
        if type(other) is Library:
            # Leveraging the uniqueness of the file system paths
            return self.path.resolve().absolute() == other.path.resolve().absolute()
        else:
            raise Exception(f"Cannot compare '{type(self)}' with type '{type(other)}'.")

    def __str__(self):
        return str(self.path.resolve().absolute())

    @staticmethod
    def is_library(file_path: Path) -> bool:
        """Determines if a file/folder defines or not a `Library`.

        Args:
            file_path (Path): a path to an existing file/folder.

        Returns:
            bool: `True` if the path points to a valid Library file/folder, `False` otherwise.

        """
        # NOTE Because of namespace packages there is not actually a way to assert if the path is a top level package,
        #  it is all relative... we can at least check if it is a package, and then potentially be a library
        return Package.is_package(file_path)

    @staticmethod
    def __get_name(library_path: Path) -> str:
        """Gets the name of the library from its file/folder.

        Args:
            library_path (Path): the path to the file/folder containing the library source.

        Returns:
            str: the name of the library.

        """
        # for a file '<parent_path>\<file_name>.<ext>' returns '<file_name>'
        # for a folder '<parent_path>\<dir_name>' returns '<dir_name>'
        return library_path.stem


class Package:
    """A representation of a Python3 package, intended as a 'module', 'regular package' or 'namespace package'.

    Attributes:
        simple_name (str): the name of only this package.
        full_name (str): the name of the package inside the library, so its fully-qualified name.
        path (Path): the path to the file/folder defining the package.
        source (Path | None): the path to the file containing the package source. Exists only for `REGULAR` and
         `MODULE` packages.
        type (Package.Type): the type of package, as defined by `Package.Type`.
        library (Library): the library of which the package is part of.
        direct_subpackages (Set[Package]): the other packages contained in the package namespace.
        ast (Module | None): the 'abstract syntax tree' related to the source code. Exists only for `REGULAR` and
         `MODULE` packages.
        # TODO DELETE individual (ontology.Package): the package's individual in the ontology.

    Notes:
        For 'module' SEE <https://docs.python.org/3/glossary.html#term-module>.
        For 'regular package' SEE <https://docs.python.org/3/glossary.html#term-regular-package>.
        For 'namespace package' SEE <https://docs.python.org/3/glossary.html#term-namespace-package>.

    """
    simple_name: str
    full_name: str
    path: Path
    source: Union[Path, None]
    type: Package.Type

    library: Library
    direct_subpackages: Set[Package]

    ast: Union[astroid.Module, None]

    # TODO DELETE individual: ontology.Package

    REGULAR_PKG_FILE_ID = "__init__.py"

    def __init__(self, package_path: Path, library: Library):
        """Creates a representation of a Python3 package.

        Args:
            package_path (Path): the path to the file/folder containing the package source.
            library (Library): the library of which the package is part of.

        Raises:
            Exception: invalid package.
        """
        package_path = package_path.resolve().absolute()

        # Check input
        package_type = Package.get_package_type(package_path)
        if package_type is Package.Type.NONE:
            raise Exception(f"Invalid package '{package_path}'.")

        # Init
        self.simple_name, self.full_name = Package.__get_name(package_path, library)
        self.path = package_path
        self.source = self.__get_source_path(package_path, package_type)
        self.type = package_type

        self.library = library
        self.direct_subpackages = set()
        if package_type is not Package.Type.MODULE:
            assert self.path.is_dir()
            for file_path in self.path.iterdir():
                if Package.is_package(file_path):
                    self.direct_subpackages.add(Package(file_path, library))

        # Add this package to its owner project
        self.library.project.packages[self.get_ref_path()] = self

        # AST creation is delayed and left for the extraction process.
        self.ast = None

        # Individual creation is delayed and left for the extraction process.
        self.individual = None

    def __hash__(self):
        return self.get_ref_path().__hash__()

    def __eq__(self, other):
        if type(other) is Package:
            # Leveraging the uniqueness of the file system paths
            return self.get_ref_path().resolve().absolute() == other.get_ref_path().resolve().absolute()
        else:
            raise Exception(f"Cannot compare '{type(self)}' with type '{type(other)}'.")

    def __str__(self):
        return str(self.get_ref_path())

    def get_ref_path(self):
        """Returns the unique identifier path.

        Returns:
            Path: the path to the source file, for REGULAR and MODULE packages, and the path to the folder for
             NAMESPACE packages.

        """
        return self.source if self.source else self.path

    class Type(Enum):
        """Possible results of package identification."""
        NONE = 0
        """Indicates a file/folder that is not a package in any way. '__init__.py' is here."""
        MODULE = 1
        """Indicates a Python module, so a '.py' file. '__init__.py' is excluded."""
        REGULAR = 2
        """Indicates a folder containing the '__init__.py' file."""
        NAMESPACE = 3
        """Indicates a folder containing no '__init__.py' file, but containing at least one `REGULAR`, `MODULE`, or
         (recursively) a `NAMESPACE` package."""

    def get_packages(self) -> Iterator[Package]:
        yield self
        for subpackage in self.direct_subpackages:
            yield from subpackage.get_packages()

    @staticmethod
    def is_package(file_path) -> bool:
        """Determines if a file/folder is a package, of any kind.

        Args:
            file_path: the path to the file/folder to check.

        Returns:
            BOOL: `True` if the path is considerable a package, `False` otherwise.

        Raises:
            Exception: nonexistent file/folder.

        """
        return Package.get_package_type(file_path) is not Package.Type.NONE

    @staticmethod
    def get_package_type(file_path: Path) -> Package.Type:
        """Classifies a file/folder accordingly to the defined type of packages.

        Args:
            file_path (Path): the path to the file/folder to check.

        Returns:
            Package.Type: the kind of package the path matches with.

        Raises:
            Exception: nonexistent file/folder.

        """
        if not file_path.exists():
            raise Exception(f"Nonexistent file/folder for path '{file_path}'.")

        if file_path.is_file():
            if file_path.name == Package.REGULAR_PKG_FILE_ID:
                # This is because "__init_.py" files are strictly bounded to the folder, and treated in a special way
                #  by the Python interpreter. Since we are linking the "__init__.py" file to the folder, we have to
                #  skip the file itself to do not count it twice.
                return Package.Type.NONE
            if file_path.suffix == ".py":
                return Package.Type.MODULE
        else:
            assert file_path.is_dir()
            for sub_file_path in file_path.iterdir():
                if sub_file_path.name == Package.REGULAR_PKG_FILE_ID:
                    return Package.Type.REGULAR
            for sub_file_path in file_path.iterdir():
                if Package.get_package_type(sub_file_path) is not Package.Type.NONE:
                    return Package.Type.NAMESPACE
        return Package.Type.NONE

    @staticmethod
    def __get_name(package_path: Path, library: Library) -> Tuple[str, str]:
        """Gets the name of the library from its file/folder.

        Args:
            package_path (Path): the path to the file/folder containing the package source.
            library (Library): the library of which the package is part of.

        Returns:
            Tuple[str, str]: the simple and full name of the package.

        Raises:
            Exception: package not in library.

        """
        if not str(package_path).startswith(str(library.path)):
            raise Exception(f"Package '{package_path}' not in Library '{library.path}'.")
        simple_name = package_path.stem
        full_name = ".".join(package_path.parent.joinpath(package_path.stem).parts[len(library.path.parts)-1:])
        return simple_name, full_name

    @staticmethod
    def __get_source_path(package_path: Path, package_type: Package.Type) -> Path:
        """Gets the path to the source file related to a package.

        Args:
            package_path (Path): the path to the file/folder defining the package.
            package_type (Package.Type): the type of package at hand.

        Returns:
            Path: the path to the related source code for `REGULAR` and `MODULE` packages, None otherwise.

        """
        if package_type is Package.Type.MODULE:
            return package_path
        if package_type is Package.Type.REGULAR:
            return package_path.joinpath(Package.REGULAR_PKG_FILE_ID)
