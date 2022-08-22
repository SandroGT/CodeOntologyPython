import re as regex

from codeontology import *
from codeontology.rdfization.python import explorer

class Project:
    individual: ontology.Project
    abs_path: str
    abs_setup_file_path: str
    libraries: Set[explorer.structure.Library]
    python: explorer.structure.Library
    dependencies: Set[explorer.structure.Library]

    _cached_projects: Dict[str, explorer.structure.Project] = dict()

    __PROJECT_SETUP_FILE = "setup.py"
    __PROJECT_CONF_FILE = "setup.cfg"

    def __init__(self, abs_path):

        # Check input
        if not abs_path:
            raise Exception("'abs_path' has not been specified")
        if not os.path.isdir(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not a valid directory")
        if not abs_path == os.path.abspath(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not an absolute path value")
        if not self.is_project(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not a valid project path")

        # Init
        assert explorer.structure.Project._cached_projects.get(abs_path, None) is None

        self.abs_path = abs_path
        self.abs_setup_file_path = os.path.join(self.abs_path, self.__PROJECT_SETUP_FILE)

        # Read the setup file
        setup_dict = self._get_setup_file_content()

        # Extract the useful content
        # SEE allowed keys for the setup file at https://setuptools.pypa.io/en/latest/references/keywords.html

        # Get libraries
        packages = setup_dict.get("packages", None)
        if not packages:
            raise Exception(f"No declared 'packages' inside '{self.abs_setup_file_path}'")
        root_libraries_names = set([pkg.split(".")[0] for pkg in packages])
        package_dir = setup_dict.get("package_dir", None)
        root_libraries_paths = set()
        if package_dir:
            src_dir = package_dir.get("", None)
            if src_dir:
                assert len(package_dir.keys()) == 1, f"Misinterpreted key 'package_dir' on '{self.abs_setup_file_path}'"
                for root_lib_name in root_libraries_names:
                    root_lib_path = os.path.join(self.abs_path, src_dir, root_lib_name)
                    assert explorer.structure.Library.is_library(root_lib_path), f"{root_lib_path} is not a 'Library' path"
                    root_libraries_paths.add(root_lib_path)
            else:
                for root_lib_name in root_libraries_names:
                    root_lib_dir = package_dir.get(root_lib_name, None)
                    assert root_lib_dir, f"Unable to find root directory for {root_lib_name} 'Library'"
                    root_lib_path = os.path.join(self.abs_path, root_lib_dir, root_lib_name)
                    assert explorer.structure.Library.is_library(root_lib_path)
                    root_libraries_paths.add(root_lib_path)
        self.libraries = set()
        for root_lib_path in root_libraries_paths:
            self.libraries.add(explorer.structure.Library(root_lib_path))

        # Get dependencies
        install_requires = setup_dict.get("install_requires", setup_dict.get("requires", None))
        # 'requires' is the deprecated version of 'install_requires', but could be found
        for requirement in install_requires:
            project_name =



        # Get Python version
        python_requires = setup_dict.get("python_requires", None)
        if python_requires:
            # Take exactly the specified version, not caring about upper or lower bounds
            python_version = glob_pypi.normalize_python_version(regex.sub(r"[<>=]", "", python_requires))
        else:
            # We automatically assume the latest if one is not specified
            # FIXME latest usually are in a 'bugfix' status, which is not ideal
            python_version = glob_pypi.norm_python_versions[0]
        assert glob_pypi.is_valid_py_version(python_version), f"Generated an invalid Python version {python_version}"
        python_abs_source_path = glob_pypi.download_python_source(python_version)
        self.python = explorer.structure.Library(python_abs_source_path)



        name = setup_dict.get("name", None)

        version = setup_dict.get("version", None)

        description = setup_dict.get("description", None)

        long_description = setup_dict.get("long_description", None)

        python_requires = setup_dict.get("python_requires", None)  # python version

        packages = setup_dict.get("packages", None)  # to find libraries

        install_requires = setup_dict.get("install_requires", None)  # dependencies
        requires = setup_dict.get("requires", None)  # deprecated version of install_requires, but could be found

        # Create individual
        # TODO

    def __hash__(self):
        return self.abs_path.__hash__()

    def __eq__(self, other):
        return self.abs_path == getattr(other, "abs_path", None)

    def _get_setup_file_content(self) -> Dict:
        from contextlib import contextmanager
        from importlib import import_module
        import setuptools
        from setuptools.config import read_configuration
        import sys
        from unittest import mock

        @contextmanager
        def safe_setup_read(abs_setup_dir):
            # Backup of current working directory, sys.stdout and sys.stderr
            saved_cwd = os.getcwd()
            saved_stdout, saved_stderr = sys.stdout, sys.stderr
            # saved_sys_modules = sys.modules.copy()

            # Move to setup directory and deactivate output prints
            os.chdir(abs_setup_dir)
            sys.stdout = sys.stderr = open(os.devnull, "w")

            try:
                yield
            finally:
                # Restore saved values
                os.chdir(saved_cwd)
                sys.stdout, sys.stderr = saved_stdout, saved_stderr
                del sys.modules[os.path.basename(self.__PROJECT_SETUP_FILE)]

        # Use mocking and a context manager to read the setup file content securely
        # SEE mocking at https://stackoverflow.com/a/24236320/13640701
        # SEE context manager at https://stackoverflow.com/a/37996581/13640701
        # SEE stop setup prints at https://stackoverflow.com/a/10321751/13640701
        with safe_setup_read(self.abs_path), mock.patch.object(setuptools, 'setup') as mock_setup:
            try:
                import_module(os.path.basename(self.__PROJECT_SETUP_FILE))
                assert mock_setup.called
                # Get the args passed to the mock object faking the 'setuptools.setup' needed for a real setup
                _, setup_dict = mock_setup.call_args
                # conf_dict = read_configuration(self.__PROJECT_CONF_FILE)  # may be useful, but not yet
                return setup_dict
            except Exception:
                raise Exception(f"Unable to securely read the '{self.abs_setup_file_path}' file content")

    @staticmethod
    def _parse_requirement(requirement: str):
        assert regex.match(r"^[\w\d.,;'<>= ]+$", requirement), f"Unexpected format for {requirement}"
        requirement = regex.sub(" ", "", requirement)
        requirement = requirement.split(";")[0]
        list_requirement = [requirement]
        if "==" in requirement: list_requirement = requirement.split("==")
        else:
            if "<" in requirement: list_requirement = requirement.split("<")
            elif ">" in requirement: list_requirement = requirement.split(">")
            if len(list_requirement) > 1:
                if "=" in list_requirement[1]:
                    assert list_requirement[1].startswith("=")
                    list_requirement[1] = list_requirement[1][1:]
        assert 1 <= len(list_requirement) <= 2
        project_name = list_requirement[0]
        project_version = list_requirement[1] if len(list_requirement) == 2 else None
        return project_name, project_version

    @staticmethod
    def is_project(abs_path) -> bool:
        assert abs_path == os.path.abspath(abs_path)
        if os.path.isdir(abs_path):
            return explorer.structure.Project.__PROJECT_SETUP_FILE in os.listdir(abs_path)
        else:
            return False


class Library:
    individual: ontology.Library
    abs_path: str
    project: explorer.structure.Project
    root_package: explorer.structure.Package
    dependencies: Set[explorer.structure.Library]

    def __init__(self, abs_path, project: explorer.structure.Project = None):

        # Check input
        if not abs_path:
            raise Exception("'abs_path' has not been specified")
        if not os.path.isdir(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not a valid directory")
        if not abs_path == os.path.abspath(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not an absolute path value")
        if not self.is_library(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not a valid library path")
        if project and not isinstance(project, explorer.structure.Project):
            raise Exception(f"Wrong 'project' type, expected 'Project', obtained '{type(project)}''")
        if project and not abs_path.startswith(project.abs_path):
            raise Exception(f"Specified path '{abs_path}' is not part of '{project.abs_path}'")

        # Init
        self.abs_path = abs_path
        self.project = project
        self.root_package = explorer.structure.Package(abs_path, self)
        self.dependencies = self.project.dependencies if self.project else None

        # Create individual
        # TODO

    def __hash__(self):
        return self.abs_path.__hash__()

    def __eq__(self, other):
        return self.abs_path == getattr(other, "abs_path", None)

    @staticmethod
    def is_library(abs_path) -> bool:
        assert abs_path == os.path.abspath(abs_path)
        return \
            os.path.isdir(abs_path) and \
            explorer.structure.Package.is_package_path(abs_path) and \
            not explorer.structure.Package.is_package_path(os.path.normpath(os.path.join(abs_path, "..")))

    def __get_de_facto_dependencies(self):
        # TODO this could be a starting point to allow to analyze libraries and not necessarily projects
        dependencies = set()
        for imported_name in self.root_package.get_imported_names():
            pass


class Package:  # or module, since ontologically speaking a module is a package
    individual: ontology.Package
    abs_path: str
    library: explorer.structure.Library
    direct_packages: Set[explorer.structure.Package]
    is_module: bool

    __PACKAGE_FILE_IDENTIFIER = "__init__.py"

    def __init__(self, abs_path: str, library: explorer.structure.Library):

        # Check input
        if not abs_path:
            raise Exception("'abs_path' has not been specified")
        if not os.path.isdir(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not a valid directory")
        if not abs_path == os.path.abspath(abs_path):
            raise Exception(f"Specified path '{abs_path}' is not an absolute path value")
        if not (self.is_package_path(abs_path) or self.is_module_path(abs_path)):
            raise Exception(f"Specified path '{abs_path}' is not a valid package or module")
        if not abs_path.startswith(library.abs_path):
            raise Exception(f"Specified path '{abs_path}' is not part of '{library.abs_path}'")
        if not library:
            raise Exception(f"Stand-alone packages (no library) are not yet supported")
        if not isinstance(library, explorer.structure.Library):
            raise Exception(f"Wrong 'library' type, expected 'Library', obtained '{type(library)}''")
        if not abs_path.startswith(library.abs_path):
            raise Exception(f"Specified path '{abs_path}' is not part of '{library.abs_path}'")

        # Init
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
                        self.direct_packages.add(explorer.structure.Package(abs_file, library))
        else:
            assert self.is_module_path(abs_path)
            self.is_module = True
            # Define only the module-package
            self.abs_path = abs_path

        # Create individual
        # TODO

    def __hash__(self):
        return self.abs_path.__hash__()

    def __eq__(self, other):
        return self.abs_path == getattr(other, "abs_path", None)

    def get_imported_names(self) -> Iterator[str]:
        # TODO
        def search_imports(node: astroid.nodes.NodeNG):
            if isinstance(node, astroid.nodes.Import):
                pass
        if self.is_module:
            # search imported names somehow
            pass
        else:
            for package in self.direct_packages:
                yield from package.get_imported_names()

    @staticmethod
    def is_package_path(abs_path) -> bool:
        assert abs_path == os.path.abspath(abs_path)
        if os.path.isdir(abs_path):
            return explorer.structure.Package.__PACKAGE_FILE_IDENTIFIER in os.listdir(abs_path)
        else:
            return False

    @staticmethod
    def is_module_path(abs_path) -> bool:
        assert abs_path == os.path.abspath(abs_path)
        if os.path.isfile(abs_path):
            return os.path.splitext(abs_path)[1] == ".py"
        else:
            return False
