import os

import astroid

from codeontology import ontology
from codeontology.rdfization.python.explore.structure import Package

class Visitor:

    package: Package
    ast: astroid.nodes.NodeNG

    def __init__(self, package: Package):
        self.package = package
        self.parse()
        self.visit_to_extract(self.ast)

    def parse(self) -> None:
        assert os.path.isfile(self.package.abs_path)
        assert self.package.abs_path == os.path.abspath(self.package.abs_path)
        module_name = self.package.individual.hasFullyQualifiedName
        assert module_name

        cached_ast = astroid.astroid_manager.MANAGER.astroid_cache.get(module_name, None)

        if cached_ast:
            assert isinstance(cached_ast, astroid.nodes.Module)
            assert cached_ast.file == self.package.abs_path, f"{cached_ast.file} is not {self.package.abs_path}"
            ast = cached_ast
            assert getattr(ast, "package", None)
        else:
            with open(self.package.abs_path, "r", encoding="utf8") as f:
                ast = astroid.parse(f.read(), path=self.package.abs_path, module_name=module_name)
            assert isinstance(ast, astroid.nodes.Module)
            assert astroid.astroid_manager.MANAGER.astroid_cache.get(module_name, None)
            # Save the package into the AST
            ast.package = self.package

        self.ast = ast

    def visit_to_extract(self, node: astroid.nodes.NodeNG) -> None:
        extract_function_name = f"_extract_{type(node).__name__}"
        extract_function = getattr(self, extract_function_name, None)
        if extract_function:
            extract_function(node)
        for child in node.get_children():
            if child:
                self.visit_to_extract(child)

    def _extract_Import(self, node: astroid.nodes.Import):
        for name, alias in node.names:
            # Some modules cannot just be imported, it's ok!
            #  For example, 'MeCab' in 'sphinx\search\ja.py' is not supposed to be there for sure, even in a correct
            #  installation!
            try:
                imported_ast = node.do_import_module(modname=name)
                assert isinstance(imported_ast, astroid.nodes.Module)
            except Exception as e:
                assert node.root().package
                print(f"\nRaised:\n{e}\nWhile reading imports in {node.root().package.abs_path}\n")
                import sys
                print(sys.path)
                sys.exit(1)
