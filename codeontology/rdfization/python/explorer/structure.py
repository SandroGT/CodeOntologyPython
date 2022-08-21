from codeontology import *
from codeontology.rdfization.python import explorer


class Project:
    individual: ontology.Project
    abs_path: str
    libraries: Set[explorer.structure.Library]
    python: explorer.structure.Project
    dependencies: Set[explorer.structure.Library]

    def __init__(self, path):
        assert self.is_project(path)
        pass

    def __hash__(self):
        return self.abs_path.__hash__()

    def __eq__(self, other):
        return self.abs_path == getattr(other, "abs_path", None)

    @staticmethod
    def is_project(path) -> bool:
        pass


class Library:
    individual: ontology.Library
    abs_path: str
    project: explorer.structure.Project
    root_package: explorer.structure.Package
    python: explorer.structure.Project
    dependencies: Set[explorer.structure.Library]

    def __init__(self, abs_path, project: explorer.structure.Project = None):
        # TODO change this asserts in proper checks
        assert abs_path
        assert abs_path == os.path.abspath(abs_path)

        # Check input
        if not self.is_library(abs_path):
            raise Exception(f"Specified directory {abs_path} is not a valid library")
        if project and not abs_path.startswith(project.abs_path):
            raise Exception(f"Specified directory {abs_path} is not part of {project.abs_path}")

        # Init
        self.abs_path = abs_path
        self.project = project
        self.python = self.project.python if self.project else explorer.structure.Project(glob_pypi.download_python_source())
        self.root_package = explorer.structure.Package(abs_path, self)
        self.__get_defacto_dependencies()

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

    def __get_defacto_dependencies(self):
        dependencies = set()
        package = self.root_package

        while package:
            pass


class Package:  # or module, since ontologically speaking a module is a package
    individual: ontology.Package
    abs_path: str
    library: explorer.structure.Library
    direct_packages: Set[explorer.structure.Package]
    is_module: bool

    __PACKAGE_FILE_IDENTIFIER = "__init__.py"

    def __init__(self, abs_path: str, library: explorer.structure.Library):
        # TODO change this asserts in proper checks
        assert abs_path
        assert abs_path == os.path.abspath(abs_path)
        assert library

        # Check input
        if not (self.is_package_path(abs_path) or self.is_module_path(abs_path)):
            raise Exception(f"Specified directory {abs_path} is not a valid package or module")
        if not abs_path.startswith(library.abs_path):
            raise Exception(f"Specified directory {abs_path} is not part of {library.abs_path}")

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

    def get_imported_packages(self) -> Iterator[str]:
        def search_imports(node: astroid.nodes.NodeNG):
            if isinstance(node, astroid.nodes.Import):
                pass
        if self.is_module:
            pass
        else:
            for package in self.direct_packages:
                yield from package.get_imported_packages()

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
