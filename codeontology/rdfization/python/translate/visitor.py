import os

import astroid

from codeontology import ontology
from codeontology.rdfization.python.explore.structure import Package

class Visitor:

    package_individual: ontology.Package

    def __init__(self, package: Package):
        self.package_individual = package.individual

    def parse(self, abs_path: str) -> astroid.nodes.NodeNG:
        assert abs_path == os.path.abspath(abs_path)
        module_name, extension = os.path.splitext(os.path.basename(abs_path))
        assert extension == ".py"

        cached_ast = astroid.astroid_manager.MANAGER.astroid_cache.get(module_name, None)

        if cached_ast:
            assert isinstance(cached_ast, astroid.nodes.Module)
            assert cached_ast.file == abs_path, f"{cached_ast.file} is not {abs_path}"
            ast = cached_ast
        else:
            with open(abs_path, "r", encoding="utf8") as f:
                ast = astroid.parse(f.read(), path=abs_path, module_name=module_name)
            assert isinstance(ast, astroid.nodes.Module)
            assert astroid.astroid_manager.MANAGER.astroid_cache.get(module_name, None)

        return ast

    def visit_to_extract(self, node: astroid.nodes.NodeNG):
        extract_function_name = f"_extract_{type(node).__name__}"
        extract_function = getattr(self, extract_function_name, None)
        if extract_function:
            extract_function(node)
        for child in node.get_children():
            if child:
                self.visit_to_extract(child)
