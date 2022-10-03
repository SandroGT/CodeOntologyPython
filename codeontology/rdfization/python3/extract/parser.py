"""Parsing functionalities."""

import astroid
import docstring_parser
from docstring_parser.common import Docstring

from codeontology import logging
from codeontology.rdfization.python3.explore import Package


def parse_source(package: Package) -> None:
    """Accesses and parses the source code related to a package, storing the AST in the `Package` object itself
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
        if cached_ast:
            ast = cached_ast
        else:
            # Fails may happen during the decoding or parsing of some Python source files. All the witnessed fails
            #  seems to come from 'test' packages anyway.
            ast = None
            try:
                with package.source.open("rb") as stream:
                    source_text = stream.read().decode()
            except Exception as e:
                logging.warning(f"Failed decoding '{package.source}' with error '{e}'.")
                source_text = None
            if source_text is not None:
                try:
                    ast = astroid.parse(source_text, path=str(package.source), module_name=package.full_name)
                except Exception as e:
                    logging.warning(f"Failed parsing '{package.source}' with error '{e}'.")
        if ast:
            package.ast = ast
            ast.package = package


def parse_comment(comment_text: str) -> Docstring:
    """Parse and structures a comment, automatically recognising the format.

    Args:
        comment_text (str): the raw text comment as a string.

    Returns:
        Docstring: a structured representation of the comment.

    """
    return docstring_parser.parse(comment_text)
