"""Python parsing functionalities."""

from pathlib import Path
from typing import Dict

import astroid
import docstring_parser
from docstring_parser.common import Docstring

from codeontology import LOGGER
from codeontology.rdfization.python3.explore import Package, Project


class Parser:
    """Parsing functionalities for the source code of a `Project`.

    Attributes:
        project (Project): the project defining the structure and location of the source files.
        parsed_packages (Dict[Path, Package]): the actually parsed packages.

    Notes:
        During parsing it adds an `ast` attribute to the parsed packages to link them with their `astroid` AST
         objects; it also adds a `package` attribute to the AST objects to link them with their package in return.

    """

    project: Project
    parsed_packages: Dict[Path, Package]  # TODO rename

    def __init__(self, project: Project):
        """Creates a `Parser` instance, parsing all the source files of the project's own libraries and packages, as
         well as those of all the dependencies that are actually imported. Does not parse source files that have been
         downloaded but are never imported effectively.

        Args:
            project (Project): the project defining the structure and location of the source files.

        """
        self.project = project
        self.parsed_packages = dict()

        for library in project.libraries:
            for package in library.root_package.get_packages():
                self.__parse_package_recursively(package, self.parsed_packages)

    def __parse_package_recursively(self, package: Package, parsed_packages: Dict[Path, Package]):
        """Accesses and parses the source code related to a `package, storing the AST in the `Package` object itself
         (in a `ast` attribute) and adding the package to the AST in return (in a `package` attribute).

        Parsing the source code will add it to the parsing library caches for future references. `Package`s are cached
         using their fully-qualified names. Reading the source file or parsing the source code may fail: in that case
         no AST is created and bounded to the package.

        Args:
            package (Package): the package to parse.
            parsed_packages (Dict[Path, Package]): the parsed packages so far.

        """
        # Only `REGULAR` and `MODULE` packages have related source code.
        if package.type in [Package.Type.REGULAR, package.Type.MODULE]:
            cached_ast = astroid.astroid_manager.MANAGER.astroid_cache.get(package.full_name, None)
            if not cached_ast:
                # Fails may happen during the decoding or parsing of some Python source files. All the witnessed fails
                #  seems to come from 'test' packages anyway.
                ast = None
                try:
                    with package.source.open("rb") as stream:
                        source_text = stream.read().decode()
                except UnicodeError as e:
                    LOGGER.warning(f"Failed decoding '{package.source}' with error '{e}'.")
                    source_text = None
                if source_text is not None:
                    try:
                        ast = astroid.parse(source_text, path=str(package.source), module_name=package.full_name)
                    except astroid.AstroidError as e:
                        LOGGER.warning(f"Failed parsing '{package.source}' with error '{e}' (error '{type(e)}').")
            else:
                ast = cached_ast
            if ast:
                package.ast = ast
                ast.package_ = package
                parsed_packages[package.source] = package
                self.__parse_imports_recursively(ast, parsed_packages)
            else:
                LOGGER.warning(f"No AST found for parsed package '{package.source}'.")

    def __parse_imports_recursively(self, node: astroid.NodeNG, parsed_packages: Dict[Path, Package]):
        """Goes through the remaining nodes of an AST to search for the actually imported `Package`s, looking at the
         'import statements': identified imported packages are then recursively parsed too.

        Args:
            node (astroid.NodeNG): a node from an `astroid` AST of a package.
            parsed_packages (Dict[Path, Package]): the parsed packages so far.

        """
        for child in node.get_children():
            to_import_names = []
            if type(child) is astroid.Import:
                for mod_name, mod_alias in child.names:
                    to_import_names.append(mod_name)
            if type(child) is astroid.ImportFrom:
                to_import_names.append(child.modname)
            for name in to_import_names:
                try:
                    ast = child.do_import_module(name)
                    assert ast
                    if not ast.file:
                        self.__reconstruct_stdlib_module_from_ast(ast)
                    ast_path = Path(ast.file)
                    package = self.project.find_package(ast_path)
                    if package and not parsed_packages.get(ast_path, None):
                        self.__parse_package_recursively(package, parsed_packages)
                except (astroid.AstroidError, AttributeError):
                    # Many modules may have failing imports, and the error is usually properly handled at runtime. It
                    #  is ok, especially if we are sure we are parsing an actually working project.
                    LOGGER.debug(f"Impossible to load AST for module '{name}' from file '{child.root().file}'")
            self.__parse_imports_recursively(child, parsed_packages)

    def __reconstruct_stdlib_module_from_ast(self, ast: astroid.Module):
        """Reconstructs a standard library source file that is not present in the downloaded Python source folder, but
         whose AST is known to `astroid`. It does it by reverse-parsing the available AST.

        Notes:
            We are dealing with a standard library module that is probably written in C, for which there is no Python
             source code; `astroid` has AST versions of the standard modules in its caches, even though in this case
             they just contain the public interface of the module with no actual implementation of methods (just a
             `pass` statement).
            For example, the `math` module is not included as `math/__init__.py` or `math.py` in the standard library
             sources, but `astroid` has an AST for its interface, with the definition of all its methods, but no
             implementation. We create the `math /__init__.py` by un-parsing the AST at hand. Creating the file for the
             AST is not fundamental, since the important thing is creating the `Library` and `Package` objects to then
             properly create the individuals related to the module: creating the file just make that task more easy
             because we are not creating special instances of those objects that are related to no source files.

        Args:
            ast (astroid.Module): an entire AST of a module.

        """
        LOGGER.debug(f"Reconstructing standard library module for '{ast.name}'.")

        package_name_parts = ast.name.split(".")
        stdlib_path = self.project.python3_path

        dir_path = stdlib_path
        for parent_part in package_name_parts:
            dir_path = dir_path.joinpath(parent_part)
            if not dir_path.exists():
                dir_path.mkdir()

        package_init_path = dir_path.joinpath(Package.REGULAR_PKG_FILE_ID)
        with open(package_init_path, 'w', encoding='utf-8') as f:
            f.write(ast.as_string())

        library_path = stdlib_path.joinpath(package_name_parts[0])
        self.project.add_or_replace_stdlib_library(library_path)

        package = self.project.find_package(package_init_path)
        ast.file = package.source
        package.ast = ast
        ast.package_ = package

    @staticmethod
    def parse_comment(comment_text: str) -> Docstring:
        """Parse and structures a comment, automatically recognising the format.

        Args:
            comment_text (str): the raw text comment as a string.

        Returns:
            Docstring: a structured representation of the comment.

        """
        return docstring_parser.parse(comment_text)
