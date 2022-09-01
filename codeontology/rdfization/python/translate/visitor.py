import os

import astroid

from codeontology import ontology
from codeontology.rdfization.python.explore.structure import Package
from codeontology.rdfization.python.translate.transforms import Transformer
from codeontology.rdfization.python.translate.individuals import Individuals


class Visitor:

    @staticmethod
    def parse(package: Package) -> None:
        assert os.path.isfile(package.abs_path)
        assert package.abs_path == os.path.abspath(package.abs_path)
        module_name = package.individual.hasFullyQualifiedName + ".py"
        assert module_name

        cached_ast = astroid.astroid_manager.MANAGER.astroid_cache.get(module_name, None)

        if cached_ast:
            assert isinstance(cached_ast, astroid.Module)
            assert cached_ast.file == package.abs_path, f"{cached_ast.file} is not {package.abs_path} [{module_name}]"
            ast = cached_ast
            assert getattr(ast, "structure_package", None)
        else:
            with open(package.abs_path, "r", encoding="utf8") as f:
                ast = astroid.parse(f.read(), path=package.abs_path, module_name=module_name)
            assert isinstance(ast, astroid.Module)
            assert astroid.astroid_manager.MANAGER.astroid_cache.get(module_name, None)
            assert ast is astroid.astroid_manager.MANAGER.astroid_cache.get(module_name)
            # Save the package into the AST
            ast.structure_package = package

        package.ast = ast

    @staticmethod
    def retrieve_or_create(node: astroid.NodeNG, attribute_name: str, creation_args_dict: dict = None):
        individual = getattr(node, attribute_name, "<unmatched>")
        if individual == "<unmatched>":
            if not creation_args_dict:
                creation_args_dict = dict()
            builder_fun = getattr(Transformer, f"transform_add_{attribute_name}")
            individual = builder_fun(node, **creation_args_dict)
        return individual

    @staticmethod
    def visit_to_extract(node: astroid.NodeNG) -> None:
        extract_function_name = f"_extract_{type(node).__name__}"
        extract_function = getattr(Visitor, extract_function_name, None)
        if extract_function:
            extract_function(node)
        for child in node.get_children():
            if child:
                Visitor.visit_to_extract(child)

    @staticmethod
    def _extract_Import(node: astroid.Import):
        for name, alias in node.names:
            try:
                # Some modules just cannot be imported, it's ok! Some imports are inside a 'try-catch' statement,
                #  acknowledging that their import could fail, even in a the right environment with all the
                #  dependencies.
                imported_ast = node.do_import_module(modname=name)
                assert isinstance(imported_ast, astroid.Module), \
                       f"wrong assumption on {imported_ast} ({type(imported_ast)})"
                file = getattr(imported_ast, "file", None)
                if file:
                    cached_file = getattr(astroid.astroid_manager.MANAGER.astroid_cache[name], "file", None)
                    if cached_file:
                        assert file == cached_file, f"{file} == {cached_file}"
            except Exception:
                pass

    @staticmethod
    def _extract_FunctionDef(node: astroid.FunctionDef):
        overrides = getattr(node, "overrides", "<unmatched>")
        if overrides == "<unmatched>":
            transform_add_method_overrides(node)
            overrides = getattr(node, "overrides", "<unmatched>")
        assert overrides != "<unmatched>"

        arguments: astroid.Arguments = node.args
        assert isinstance(arguments, astroid.Arguments), f"{type(arguments)}"
        class_annotations = getattr(arguments, "class_annotations", "<unmatched>")
        if class_annotations == "<unmatched>":
            transform_add_method_args_type(node)
            class_annotations = getattr(arguments, "class_annotations", "<unmatched>")
        assert class_annotations != "<unmatched>" and isinstance(class_annotations, list)
        assert len(arguments.class_annotations) == len(arguments.annotations)

    @staticmethod
    def _extract_ClassDef(node: astroid.ClassDef):
        class_individual = getattr(node, "class_individual", "<unmatched>")
        if class_individual == "<unmatched>":
            class_individual = build_class_individual(node)
