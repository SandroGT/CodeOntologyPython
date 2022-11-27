"""Python parsing functionalities."""

from pathlib import Path
from typing import Iterator, Set

import astroid
import docstring_parser
from docstring_parser.common import Docstring

from codeontology import logging
from codeontology.rdfization.python3.explore import Project, Package


class Parser:

    project: Project
    project_related_packages_for_real: Set  # TODO rename

    def __init__(self, project: Project):
        self.project = project
        self.project_related_packages_for_real = set()  # On these I apply the Transformer
        # But I run the serialization natively just on the Project packages
        for library in project.libraries:
            for package in library.root_package.get_packages():
                for pkg in self.__parse_recursively(package):
                    self.project_related_packages_for_real.add(pkg)

    def __parse_recursively(self, package: Package) -> Iterator[Package]:
        """TODO adapt
        Accesses and parses the source code related to a package, storing the AST in the `Package` object itself
         ('.ast' attribute) and adding the `Package` to the AST too ('.package' attribute).
        Parsing the source code will add it to the parsing library caches for future references. Packages are cached
         using their fully-qualified names.
        Reading the source file or parsing the source code may fail: in that case no AST is created and bounded to the
         `Package`.

        Args:
            package (Package): the package to parse.

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
                except Exception as e:
                    logging.warning(f"Failed decoding '{package.source}' with error '{e}'.")
                    source_text = None
                if source_text:
                    try:
                        ast = astroid.parse(source_text, path=str(package.source), module_name=package.full_name)
                    except Exception as e:
                        logging.warning(f"Failed parsing '{package.source}' with error '{e}'.")
                if ast:
                    package.ast = ast
                    ast.package = package
                    yield package
                    yield from self.__yield_import_asts(ast)

    def __yield_import_asts(self, node: astroid.NodeNG) -> Iterator[Package]:
        for child in node.get_children():
            if isinstance(child, astroid.Import):
                for mod_name, mod_alias in child.names:
                    ast = child.do_import_module(mod_name)
                    if not ast:
                        logging.warning(f"Missing AST for module {mod_name} from file {child.root().file}")
                        continue
                    if ast and not ast.file:
                        self.__reconstruct_stdlib_module_from_ast(ast)
                        continue
                    ast_path = Path(ast.file)
                    package = self.project.find_package(ast_path)
                    if package:
                        self.__parse_recursively(package)
                        if package.ast:
                            yield from self.__yield_import_asts(package.ast)
            if isinstance(child, astroid.ImportFrom):
                # TODO
                # print(child)
                pass
            yield from self.__yield_import_asts(child)

    def __reconstruct_stdlib_module_from_ast(self, ast: astroid.Module):
        # A standard library module, probably written in C, for which there is no Python source code
        # `astroid` has in its caches AST version of the standard modules, with just the interface (
        #  class and method definitions, but no implementations (pass). We construct a placeholder
        #  module from there with un-parsing!
        # Example: the `math` module is not included as `math\__init__.py` or `math.py` in the standard library sources,
        #  because it is entirely written in C. astroid has an AST for its interface anyway, with the defintion of all
        #  its methods, but no implementation (just a `pass` inside). We create the `math\__init__.py` un-parsing the
        #  AST at our hands. Creating the file is not so much important, the importan thing is creating the Library and
        #  Package objects to properly create the individuals representing this module. Creating the file just make that
        #  more easy 'cause we do not change much code.
        package_parts = ast.name.split(".")

        lib_path = self.project.python3_path.joinpath(package_parts[0])

        dir_path = self.project.python3_path
        for parent_part in package_parts:
            dir_path.joinpath(parent_part)
            init_path = dir_path.joinpath(Package.REGULAR_PKG_FILE_ID)
            if not lib_path.exists():
                lib_path.mkdir()
                if not init_path.exists():
                    init_path.touch()
        module_path = dir_path.joinpath(Package.REGULAR_PKG_FILE_ID)
        assert not module_path.exists()
        # TODO Write AST on file `module_path`
        library_package = self.project.find_package(lib_path)
        module_package = self.project.find_package(module_path)
        assert not module_package
        if not library_package:
            # TODO Create library (library creation automatically creates the packages)
            pass
        else:
            # TODO Add new package to the existing library
            pass
        module_package = self.project.find_package(module_path)
        assert module_package
        # TODO assign the AST to the Package and the Package to the AST

    @staticmethod
    def parse_comment(comment_text: str) -> Docstring:
        """Parse and structures a comment, automatically recognising the format.

        Args:
            comment_text (str): the raw text comment as a string.

        Returns:
            Docstring: a structured representation of the comment.

        """
        return docstring_parser.parse(comment_text)
