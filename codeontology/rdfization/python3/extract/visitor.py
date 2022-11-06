"""Classes and methods to visit the AST nodes and extract the related RDF triples."""

from astroid.nodes import *

from codeontology.rdfization.python3.extract.individuals import CodeIndividuals


class Visitor:
    """A collection of methods for the operations to perform on different types of AST nodes."""

    @staticmethod
    def visit_to_extract(node: NodeNG) -> None:
        extract_function_name = f"_extract_{type(node).__name__}"
        extract_function = getattr(Visitor, extract_function_name, None)
        if extract_function:
            extract_function(node)
        for child in node.get_children():
            if child:
                Visitor.visit_to_extract(child)

    @staticmethod
    def _extract_ClassDef(node: ClassDef):
        """Operations to perform on a 'ClassDef' node.

        Args:
            node (ClassDef): input node.

        """
        class_individual = getattr(node, "class_individual", "<unmatched>")
        assert class_individual == "<unmatched>"
        node.class_individual = CodeIndividuals.build_class_individual(node)

    @staticmethod
    def _extract_FunctionDef(node: FunctionDef):
        """Operations to perform on a 'FunctionDef' node.

        Args:
            node (FunctionDef): input node.

        """
        if node.is_method() and node.name == "__init__":
            constructor_individual = getattr(node, "constructor_individual", "<unmatched>")
            assert constructor_individual == "<unmatched>"
            node.constructor_individual = CodeIndividuals.build_constructor_individual(node)
        elif node.is_method():
            method_individual = getattr(node, "method_individual", "<unmatched>")
            assert method_individual == "<unmatched>"
            node.method_individual = CodeIndividuals.build_method_individual(node)

    @staticmethod
    def _extract_Arguments(node: Arguments):
        """Operations to perform on a 'Arguments' node.

        Args:
            node (Arguments): input node.

        """
        method_constructor_class = node.scope()
        # CAVEAT we are doing only methods for now, not functions
        if isinstance(method_constructor_class, FunctionDef) and method_constructor_class.is_method():
            parameters_individuals = getattr(node, "parameters_individuals", "<unmatched>")
            assert parameters_individuals == "<unmatched>"
            node.parameters_individuals = CodeIndividuals.build_parameters_individual(node)
