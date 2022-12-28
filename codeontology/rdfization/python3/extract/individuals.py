"""Classes and methods to create and instantiate ontology individuals."""

from __future__ import annotations

from typing import List, Union

import astroid

from codeontology.ontology import ontology
from codeontology.rdfization.python3.explore import Project, Library, Package
from codeontology.rdfization.python3.extract.parser import Parser


class Individuals:
    """Class to initialize the individuals from the ontology.
    Has a collection of methods, one for every class in the ontology.
    Upon creating the individual and properly appending it to the node, it instantiate the basic properties that can
    be determined by the attributes of the node itself (so no properties that involve two different individuals or
    data properties whose value depends on more than 1 AST node). The other kind of properties are instantiated by the
    extracotr itself.

    !!! using automatically generated IRIs for individuals, could be useful to specify a rule for every class?
    """

    @staticmethod
    def init_project(project: Project):
        project.individual = ontology.Project()

        project.individual.hasName = project.name
        # TODO `project.individual.hasBuildFile`, retrieving the content of the setup file
        # TODO `project.individual.hasComment`, retrieving the description from the setup file

    @staticmethod
    def init_library(library: Library):
        library.individual = ontology.Library()

        library.individual.hasName = library.name

        if library.is_by_project:
            library.individual.hasProject = library.project.individual
            library.individual.isDependencyOf.append(library.project.individual)

    @staticmethod
    def init_code_element():
        pass

    @staticmethod
    def init_package(package: Package):
        if getattr(package, "individual", NonExistent) is NonExistent:
            package.individual = ontology.Package()

            package.individual.hasSimpleName = package.simple_name
            package.individual.hasFullyQualifiedName = package.full_name

            if getattr(package.library, "individual", NonExistent) is NonExistent:
                Individuals.init_library(package.library)
            package.individual.hasLibrary = package.library.individual

            # package.individual.hasSourceCode = package.ast.as_string()
            if package.ast.doc_node:
                docstring = Parser.parse_comment(package.ast.doc_node.value)
                short_description = docstring.short_description if docstring.short_description else ""
                package.individual.hasDocumentation.append(short_description)

    @staticmethod
    def init_access_modifier():
        pass

    @staticmethod
    def init_annotation():
        pass

    @staticmethod
    def init_anonymous_class():
        pass

    @staticmethod
    def init_array_type():
        pass

    @staticmethod
    def init_assert_statement():
        pass

    @staticmethod
    def init_assignment_expression():
        pass

    @staticmethod
    def init_block_statement():
        pass

    @staticmethod
    def init_branching_statement():
        pass

    @staticmethod
    def init_break_statement():
        pass

    @staticmethod
    def init_case_labeled_block():
        pass

    @staticmethod
    def init_catch_statement():
        pass

    @staticmethod
    def init_class(class_node: astroid.ClassDef):
        if getattr(class_node, "individual", NonExistent) is NonExistent:
            class_node.individual = ontology.Class()

            class_node.individual.hasSimpleName = class_node.name

            if class_node.doc_node:
                docstring = Parser.parse_comment(class_node.doc_node.value)
                short_description = docstring.short_description if docstring.short_description else ""
                class_node.individual.hasDocumentation.append(short_description)

    @staticmethod
    def init_class_instance_creation_expression():
        pass

    @staticmethod
    def init_complex_type():
        pass

    @staticmethod
    def init_constructor():
        pass

    @staticmethod
    def init_continue_statement():
        pass

    @staticmethod
    def init_control_flow_statement():
        pass

    @staticmethod
    def init_decision_making_statement():
        pass

    @staticmethod
    def init_declaration_statement(node: astroid.NodeNG):
        if getattr(node, "stmt_individual", NonExistent) is NonExistent:
            node.stmt_individual = ontology.DeclarationStatement()
            node.stmt_individual.hasSourceCode = node.as_string()
            node.stmt_individual.hasLine = node.lineno

    @staticmethod
    def init_default_labeled_block():
        pass

    @staticmethod
    def init_do_while_statement():
        pass

    @staticmethod
    def init_enum():
        pass

    @staticmethod
    def init_exception_handling_statement():
        pass

    @staticmethod
    def init_executable():
        pass

    @staticmethod
    def init_executable_argument():
        pass

    @staticmethod
    def init_executable_invocation_expression():
        pass

    @staticmethod
    def init_expression():
        pass

    @staticmethod
    def init_expression_statement():
        pass

    @staticmethod
    def init_field():
        pass

    @staticmethod
    def init_field_declaration_statement():
        pass

    @staticmethod
    def init_finally_statement():
        pass

    @staticmethod
    def init_for_each_statement():
        pass

    @staticmethod
    def init_for_statement():
        pass

    @staticmethod
    def init_function():
        pass

    @staticmethod
    def init_function_invocation_expression():
        pass

    @staticmethod
    def init_global_variable():
        pass

    @staticmethod
    def init_global_variable_declaration_statement():
        pass

    @staticmethod
    def init_if_then_else_statement():
        pass

    @staticmethod
    def init_import_statement(import_node: Union[astroid.Import, astroid.ImportFrom]):
        if getattr(import_node, "stmt_individual", NonExistent) is NonExistent:
            import_node.stmt_individual = ontology.ImportStatement()
            import_node.stmt_individual.hasSourceCode = import_node.as_string()
            import_node.stmt_individual.hasLine = import_node.lineno

    @staticmethod
    def init_interface():
        pass

    @staticmethod
    def init_labeled_block():
        pass

    @staticmethod
    def init_lambda_expression():
        pass

    @staticmethod
    def init_lambda_invocation_expression():
        pass

    @staticmethod
    def init_local_variable():
        pass

    @staticmethod
    def init_local_variable_declaration_statement():
        pass

    @staticmethod
    def init_loop_statement():
        pass

    @staticmethod
    def init_method():
        pass

    @staticmethod
    def init_method_invocation_expression():
        pass

    @staticmethod
    def init_modifiable():
        pass

    @staticmethod
    def init_modifier():
        pass

    @staticmethod
    def init_parameter():
        pass

    @staticmethod
    def init_parameterized_type():
        pass

    @staticmethod
    def init_primitive_type():
        pass

    @staticmethod
    def init_return_statement():
        pass

    @staticmethod
    def init_statement():
        pass

    @staticmethod
    def init_switch_statement():
        pass

    @staticmethod
    def init_synchronized_statement():
        pass

    @staticmethod
    def init_throw_statement():
        pass

    @staticmethod
    def init_try_statement():
        pass

    @staticmethod
    def init_type():
        pass

    @staticmethod
    def init_type_argument():
        pass

    @staticmethod
    def init_type_variable():
        pass

    @staticmethod
    def init_variable():
        pass

    @staticmethod
    def init_variable_declaration_statement():
        pass

    @staticmethod
    def init_while_statement():
        pass

    @staticmethod
    def init_wildcard():
        pass


class NonExistent:
    pass
