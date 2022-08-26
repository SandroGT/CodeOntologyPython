import os

import astroid

from codeontology import ontology
from codeontology.rdfization.python.explore.structure import Package


class Visitor:

    @staticmethod
    def parse(package: Package) -> None:
        assert os.path.isfile(package.abs_path)
        assert package.abs_path == os.path.abspath(package.abs_path)
        module_name = package.individual.hasFullyQualifiedName
        assert module_name

        cached_ast = astroid.astroid_manager.MANAGER.astroid_cache.get(module_name, None)

        if cached_ast:
            assert isinstance(cached_ast, astroid.nodes.Module)
            assert cached_ast.file == package.abs_path, f"{cached_ast.file} is not {package.abs_path} [{module_name}]"
            ast = cached_ast
            assert getattr(ast, "package", None)
        else:
            with open(package.abs_path, "r", encoding="utf8") as f:
                ast = astroid.parse(f.read(), path=package.abs_path, module_name=module_name)
            assert isinstance(ast, astroid.nodes.Module)
            assert astroid.astroid_manager.MANAGER.astroid_cache.get(module_name, None)
            assert ast is astroid.astroid_manager.MANAGER.astroid_cache.get(module_name)
            # Save the package into the AST
            ast.structure_package = package

        package.ast = ast

    @staticmethod
    def visit_to_extract(node: astroid.nodes.NodeNG) -> None:
        extract_function_name = f"_extract_{type(node).__name__}"
        extract_function = getattr(Visitor, extract_function_name, None)
        if extract_function:
            extract_function(node)
        for child in node.get_children():
            if child:
                Visitor.visit_to_extract(child)

    @staticmethod
    def _extract_Import(node: astroid.nodes.Import):
        for name, alias in node.names:
            try:
                # Some modules just cannot be imported, it's ok! Some imports are inside a 'try-catch' statement,
                #  acknowledging that their import could fail, even in a the right environment with all the dependencies.
                imported_ast = node.do_import_module(modname=name)
                assert isinstance(imported_ast, astroid.nodes.Module), \
                       f"wrong assumption on {imported_ast} ({type(imported_ast)})"
                file = getattr(imported_ast, "file", None)
                if file:
                    cached_file = getattr(astroid.astroid_manager.MANAGER.astroid_cache[name], "file", None)
                    assert file == cached_file, f"{file} == {cached_file}"
            except Exception:
                pass
