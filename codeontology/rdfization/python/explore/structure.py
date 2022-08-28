from __future__ import annotations
import os
import re as regex
import shutil
from typing import Dict, Iterator, Set, Tuple, List

from codeontology import ontology
from codeontology.rdfization.python import global_pypi


class Project:
    individual: ontology.Project
    abs_project_path: str
    abs_install_path: str
    abs_setup_file_path: str
    name: str
    version: str
    libraries: Set[Library]
    python: Set[Library]
    dependencies: Set[Library]

    __PROJECT_SETUP_FILE = "setup.py"

    def __init__(self,
                 download_target: str,
                 abs_project_path: str,
                 abs_install_path: str,
                 installed_packages: List[str]):

        # Check input
        if len(download_target.split("==")) != 2:
            raise Exception(f"Invalid download target '{download_target}'")
        if not os.path.isdir(abs_project_path):
            raise Exception(f"Specified path '{abs_project_path}' is not a valid directory")
        if not abs_project_path == os.path.abspath(abs_project_path):
            raise Exception(f"Specified path '{abs_project_path}' is not an absolute path value")
        if not Project.is_project(abs_project_path):
            raise Exception(f"Specified path '{abs_project_path}' is not a valid project path")
        if not os.path.isdir(abs_install_path):
            raise Exception(f"Specified path '{abs_install_path}' is not a valid directory")
        if not abs_install_path == os.path.abspath(abs_install_path):
            raise Exception(f"Specified path '{abs_install_path}' is not an absolute path value")

        # Init
        self.individual = ontology.Project()
        self.abs_project_path = abs_project_path
        self.abs_install_path = abs_install_path
        install_path_files = {file for file in os.listdir(self.abs_install_path)}
        self.abs_setup_file_path = os.path.join(self.abs_project_path, self.__PROJECT_SETUP_FILE)

        # Read the setup file
        setup_dict = self._get_setup_file_content()
        # SEE allowed keys for the setup file at https://setuptools.pypa.io/en/latest/references/keywords.html

        # Get project name and version from setup
        name = setup_dict.get("name", "")
        if not name:
            name = download_target.split("==")[0]
        version = setup_dict.get("version", "")
        if not version:
            version = download_target.split("==")[1]

        # Get Python version and Python libraries
        self.python = set()
        python_requires = setup_dict.get("python_requires", None)
        if python_requires:
            # Take exactly the specified version, not caring about upper or lower bounds
            python_version = global_pypi.normalize_python_version(regex.sub(r"[<>=]", "", python_requires))
        else:
            # We automatically assume the latest if one is not specified
            # FIXME latest Python versions usually are in a 'bugfix' status, which is not ideal
            python_version = global_pypi.norm_python_versions[0]
        if not global_pypi.is_valid_py_version(python_version):
            raise Exception(f"Generated an invalid Python version '{python_version}'")
        python_abs_source_path = global_pypi.download_python_source(python_version)
        python_abs_source_content = {os.path.join(python_abs_source_path, file) for file in os.listdir(python_abs_source_path)}
        for file in os.listdir(python_abs_source_path):
            abs_file = os.path.join(python_abs_source_path, file)
            if Library.is_library(abs_file):
                self.python.add(Library(abs_file))

        # Get root packages (libraries) from setup
        packages = setup_dict.get("packages", None)
        if not packages:
            packages = [name]
        root_packages_names = set([pkg.split(".")[0] for pkg in packages])
        package_dir = setup_dict.get("package_dir", None)
        root_libraries_paths = set()
        if package_dir:
            source_dir = package_dir.get("", None)
            if source_dir:
                assert len(package_dir.keys()) == 1, f"Misinterpreted key 'package_dir' on '{self.abs_setup_file_path}'"
                for root_pkg_name in root_packages_names:
                    root_lib_path = os.path.join(self.abs_project_path, source_dir, root_pkg_name)
                    assert Library.is_library(root_lib_path), f"{root_lib_path} is not a 'Library' path"
                    root_libraries_paths.add(root_lib_path)
            else:
                for root_pkg_name in root_packages_names:
                    root_lib_dir = package_dir.get(root_pkg_name, None)
                    assert root_lib_dir, f"Unable to find root directory for {root_pkg_name} 'Library'"
                    root_lib_path = os.path.join(self.abs_project_path, root_lib_dir, root_pkg_name)
                    assert Library.is_library(root_lib_path)
                    root_libraries_paths.add(root_lib_path)
        else:
            # If not specified, search for a directory named after the project
            def search_for_root(abs_path: str) -> str:
                for file in os.listdir(abs_path):
                    abs_file = os.path.join(abs_path, file)
                    if os.path.isdir(abs_file) and file.lower() == name.lower() or \
                            os.path.isfile(abs_file) and file.lower() == name.lower() + ".py":
                        return abs_file
                for file in os.listdir(abs_path):
                    abs_file = os.path.join(abs_path, file)
                    if os.path.isdir(abs_file):
                        search_result = search_for_root(abs_file)
                        if search_result:
                            return search_result
            root_lib_path = search_for_root(self.abs_project_path)
            assert root_lib_path, f"some library root should be found in '{self.abs_project_path}'"
            root_libraries_paths.add(root_lib_path)
        if not root_libraries_paths:
            raise Exception(f"Cannot have no libraries in {self.abs_project_path}")
        for root_lib_path in root_libraries_paths:
            assert os.path.basename(root_lib_path) in install_path_files

        libraries_paths = set()
        libraries_names = set()
        self.libraries = set()
        for root_lib_path in root_libraries_paths:
            assert os.path.basename(root_lib_path) in install_path_files, f"'{os.path.basename(root_lib_path)}' not in {self.abs_install_path} ({install_path_files})"
            assert Package.is_package_path(root_lib_path), f"'{root_lib_path}' is not a 'Package'"
            libraries_paths.add(root_lib_path)
            libraries_names.add(os.path.splitext(os.path.basename(root_lib_path))[0])
            self.libraries.add(Library(root_lib_path, self))

        # Find the distribution files of the installed dependencies
        installed_distributions = set()
        for file in install_path_files:
            if file.endswith("dist-info"):
                abs_file = os.path.join(abs_install_path, file)
                assert os.path.isdir(abs_file), f"{abs_file}"
                lib_distribution_files = set()
                if "top_level.txt" in os.listdir(abs_file):
                    with open(os.path.join(abs_file, "top_level.txt"), "r", encoding="utf8") as f:
                        for line in f.readlines():
                            content = line.strip()
                            if content:
                                lib_distribution_files.add(content)
                else:
                    lib_distribution_files.add(file.split("-")[0])
                assert lib_distribution_files
                checked_lib_distribution_files = set()
                for distr_file in lib_distribution_files:
                    abs_distr_file = os.path.join(abs_install_path, distr_file)
                    if os.path.isdir(abs_distr_file):
                        checked_lib_distribution_files.add(distr_file)
                    else:
                        abs_distr_file += ".py"
                        if os.path.isfile(abs_distr_file):
                            checked_lib_distribution_files.add(distr_file)
                assert checked_lib_distribution_files
                for distr_file in checked_lib_distribution_files:
                    installed_distributions.add(distr_file)

        # Get dependencies from the setup
        install_requires = setup_dict.get("install_requires", setup_dict.get("requires", None))
        if install_requires:
            # Nothing to check with that info for now, since not all the specified requirements always get installed,
            # and this is not necessarily a problem, especially if they dont respect requirements
            pass

        # Get dependencies from installed packages
        self.dependencies = set()
        for distribution in installed_distributions:
            assert "-" not in distribution, f"{distribution}"

            # Get absolute path
            abs_distribution_path = os.path.join(abs_install_path, distribution)

            # Skip installed project, use the source
            if distribution in libraries_names:
                shutil.rmtree(abs_distribution_path)
                continue

            # Search libraries in that distribution
            if not os.path.isdir(abs_distribution_path):
                abs_distribution_path += ".py"
                assert os.path.isfile(abs_distribution_path) and Library.is_library(abs_distribution_path)
            assert os.path.exists(abs_distribution_path)
            new_paths = {abs_distribution_path}
            while new_paths:
                to_check = new_paths.copy()
                new_paths = set()
                for abs_path in to_check:
                    if Library.is_library(abs_path):
                        self.dependencies.add(Library(abs_path))
                    else:
                        assert os.path.isdir(abs_path)
                        for file in os.listdir(abs_path):
                            new_paths.add(os.path.join(abs_path, file))

        # TODO add a way to add dependencies from reading the import statements in the packages. Some modules, like
        #  testing modules, imports libraries that are not declared in the setup dependencies, since they contain code
        #  supposed to be run only for testing and not for normal use. This way we are missing the chance to get their
        #  triples.

        # Complete individual info

        self.individual.hasBuildFile = self.__PROJECT_SETUP_FILE

        for library in self.python:
            assert isinstance(library, Library)
            self.individual.hasDependency.append(library.individual)
            assert self.individual in library.individual.isDependencyOf
        for library in self.dependencies:
            self.individual.hasDependency.append(library.individual)
            assert self.individual in library.individual.isDependencyOf

        self.name = name
        self.version = version
        self.individual.hasName = f"{name}-{version}"

        description = setup_dict.get("description", None)
        if description:
            self.individual.hasComment = description
        long_description = setup_dict.get("long_description", None)
        if long_description:
            self.individual.hasComment = long_description

        # Check properties

        for library in self.libraries:
            assert library.individual in self.individual.isProjectOf

    def __hash__(self):
        return self.abs_project_path.__hash__()

    def __eq__(self, other):
        return self.abs_project_path == getattr(other, "abs_path", None)

    def get_packages(self) -> Iterator[Package]:
        for library in self.libraries:
            yield from library.root_package.get_packages()

    def _get_setup_file_content(self) -> Dict:
        from contextlib import contextmanager
        from importlib import import_module
        import setuptools
        import sys
        from unittest import mock

        @contextmanager
        def safe_setup_read(abs_setup_dir):
            # Backup sys.stdout and sys.stderr
            saved_stdout, saved_stderr = sys.stdout, sys.stderr
            # Add current setup directory to sys.path to find it on import
            sys.path.insert(0, abs_setup_dir)

            # Move to setup directory and deactivate output prints
            os.chdir(abs_setup_dir)
            sys.stdout = sys.stderr = open(os.devnull, "w")

            try:
                yield

            finally:
                # Restore previous values
                sys.stdout, sys.stderr = saved_stdout, saved_stderr
                sys.path = sys.path[1:]
                if sys.modules.get(os.path.splitext(self.__PROJECT_SETUP_FILE)[0], None):
                    # Delete the imported module from the cache to not retrieve it again when we try to import other
                    #  setups for other projects
                    del sys.modules[os.path.splitext(self.__PROJECT_SETUP_FILE)[0]]

        # Use mocking and a context manager to read the setup file content securely
        # SEE mocking at https://stackoverflow.com/a/24236320/13640701
        # SEE context manager at https://stackoverflow.com/a/37996581/13640701
        # SEE stop setup prints at https://stackoverflow.com/a/10321751/13640701
        fail = False
        with safe_setup_read(self.abs_project_path), mock.patch.object(setuptools, 'setup') as mock_setup:
            try:
                # IDEA Another option could be to use subprocess to read it
                import_module(os.path.splitext(self.__PROJECT_SETUP_FILE)[0])
                assert mock_setup.called
                # Get the args passed to the mock object faking the 'setuptools.setup' needed for a real setup
                _, setup_dict = mock_setup.call_args
                # conf_dict = read_configuration(self.__PROJECT_CONF_FILE)  # may be useful, but not yet
                return setup_dict
            except Exception:
                fail = True
        if fail:
            raise Exception(f"Unable to securely read the '{self.abs_setup_file_path}' file content")

    @staticmethod
    def _parse_requirement(requirement: str) -> Tuple[str, Tuple[str, str], Tuple[str, str]]:
        def extract_project_versions(versions: str) -> Tuple[str, str]:
            upper_limit: str = ""
            lower_limit: str = ""
            if versions:
                if "," in versions:
                    assert ">" in versions and "<" in versions, f"{versions}"
                    lower_limit, upper_limit = tuple(versions.split(","))
                else:
                    if ">" in versions:
                        lower_limit = versions
                    else:
                        assert "<" in versions
                        upper_limit = versions
            return lower_limit, upper_limit

        def extract_python_versions(other_requirements: str) -> Tuple[str, str]:
            match_python_version_lower = regex.search(r"(?<=python_version)>=?'[\d.]+'", other_requirements)
            python_version_lower = ""
            if match_python_version_lower:
                python_version_lower = regex.sub(r"'", r"", match_python_version_lower.group())
            match_python_version_upper = regex.search(r"(?<=python_version)<=?'[\d.]+'", other_requirements)
            python_version_upper = ""
            if match_python_version_upper:
                python_version_upper = regex.sub(r"'", r"", match_python_version_upper.group())
            return python_version_lower, python_version_upper

        assert regex.match(r"^[\w\d\-.,;'<>= ]+$", requirement), f"Unexpected format for {requirement}"
        # Get rid of optional spaces
        requirement = regex.sub(r" ", r"", requirement)

        # Match project name
        match_name = regex.search(r"^[^<>=]*", requirement)
        project_name = requirement[0:match_name.span()[1]]
        requirement = requirement[match_name.span()[1]:]

        # Match project versions
        match_versions = regex.search(r"^[^;]*", requirement)
        project_versions = extract_project_versions(requirement[0:match_versions.span()[1]])
        requirement = requirement[match_versions.span()[1]:]

        # Match python versions
        python_versions = extract_python_versions(requirement)

        return project_name, project_versions, python_versions

    @staticmethod
    def is_project(abs_path) -> bool:
        assert abs_path == os.path.abspath(abs_path)
        if os.path.isdir(abs_path):
            return Project.__PROJECT_SETUP_FILE in os.listdir(abs_path)
        else:
            return False


class Library:
    individual: ontology.Library
    abs_path: str
    project: Project
    root_package: Package

    def __init__(self, abs_path, project: Project = None):

        # Check input
        if not abs_path:
            raise Exception("'abs_path' has not been specified")
        if not abs_path == os.path.abspath(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not an absolute path value")
        if not Library.is_library(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not a valid library path")
        if project and not isinstance(project, Project):
            raise Exception(f"Wrong 'project' type, expected 'Project', obtained '{type(project)}''")
        if project and not abs_path.startswith(project.abs_project_path):
            raise Exception(f"Specified path '{abs_path}' is not part of '{project.abs_project_path}'")

        # Init
        self.individual = ontology.Library()
        self.abs_path = abs_path
        self.project = project
        self.root_package = Package(abs_path, self)

        # Complete individual info

        self.individual.hasName = Library.build_name(self.abs_path)

        if self.project:
            self.individual.hasProject = project.individual

        # Check properties

        for package in self.root_package.get_packages():
            assert package.individual in self.individual.isLibraryOf

    def __hash__(self):
        return self.abs_path.__hash__()

    def __eq__(self, other):
        return self.abs_path == getattr(other, "abs_path", None)

    @staticmethod
    def build_name(abs_path: str) -> str:
        if Package.is_package_path(abs_path):
            return abs_path.split(os.path.sep)[-1]
        else:
            assert Package.is_module_path(abs_path)
            return os.path.splitext(abs_path.split(os.path.sep)[-1])[0]

    @staticmethod
    def is_library(abs_path) -> bool:
        assert abs_path == os.path.abspath(abs_path)
        return \
            (Package.is_package_path(abs_path) or Package.is_module_path(abs_path)) and \
            not Package.is_package_path(os.path.normpath(os.path.join(abs_path, "..")))


class Package:  # or module, since ontologically speaking a module is a package
    individual: ontology.Package
    abs_path: str
    library: Library
    direct_packages: Set[Package]
    is_module: bool

    __PACKAGE_FILE_IDENTIFIER = "__init__.py"

    def __init__(self, abs_path: str, library: Library):

        # Check input
        if not abs_path:
            raise Exception("'abs_path' has not been specified")
        if not os.path.isdir(abs_path) and not os.path.isfile(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not a valid file or directory")
        if not abs_path == os.path.abspath(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not an absolute path value")
        if not (Package.is_package_path(abs_path) or Package.is_module_path(abs_path)):
            raise Exception(f"Specified path '{abs_path}' is not a valid package or module")
        if not abs_path.startswith(library.abs_path):
            raise Exception(f"Specified path '{abs_path}' is not part of '{library.abs_path}'")
        if not library:
            raise Exception(f"Stand-alone packages (no library) are not yet supported")
        if not isinstance(library, Library):
            raise Exception(f"Wrong 'library' type, expected 'Library', obtained '{type(library)}''")
        if not abs_path.startswith(library.abs_path):
            raise Exception(f"Specified path '{abs_path}' is not part of '{library.abs_path}'")

        # Init
        self.individual = ontology.Package()
        self.abs_path = ""
        self.library = library
        self.direct_packages = set()
        if self.is_package_path(abs_path):
            self.is_module = False
            # Define the package and recursively its sub-packages
            for file in os.listdir(abs_path):
                if file == self.__PACKAGE_FILE_IDENTIFIER:
                    self.abs_path = os.path.join(abs_path, self.__PACKAGE_FILE_IDENTIFIER)
                else:
                    abs_file = os.path.join(abs_path, file)
                    if self.is_package_path(abs_file) or self.is_module_path(abs_file):
                        self.direct_packages.add(Package(abs_file, library))
        else:
            assert self.is_module_path(abs_path)
            self.is_module = True
            # Define only the module-package
            self.abs_path = abs_path

        # Complete individual info

        self.individual.hasFullyQualifiedName = \
            Package.build_full_name(self.abs_path, self.library.abs_path)

        self.individual.hasSimpleName = self.individual.hasFullyQualifiedName.split(".")[-1]

        self.individual.hasLibrary = library.individual

    def __hash__(self):
        return self.abs_path.__hash__()

    def __eq__(self, other):
        return self.abs_path == getattr(other, "abs_path", None)

    def get_packages(self) -> Iterator[Package]:
        yield self
        for sub_package in self.direct_packages:
            yield from sub_package.get_packages()

    @staticmethod
    def build_full_name(abs_path: str, library_path: str) -> str:
        library_name = Library.build_name(library_path)
        return library_name + os.path.splitext(abs_path)[0].split(library_name)[-1].replace(os.path.sep, ".")

    @staticmethod
    def is_package_path(abs_path) -> bool:
        assert abs_path == os.path.abspath(abs_path)
        if os.path.isdir(abs_path):
            return Package.__PACKAGE_FILE_IDENTIFIER in os.listdir(abs_path)
        else:
            return False

    @staticmethod
    def is_module_path(abs_path) -> bool:
        assert abs_path == os.path.abspath(abs_path)
        if os.path.isfile(abs_path):
            return os.path.splitext(abs_path)[1] == ".py"
        else:
            return False
