"""Classes and methods to create and instantiate ontology individuals."""

from __future__ import annotations

from typing import List, Union

import astroid

from codeontology.ontology import ontology
from codeontology.rdfization.python3.explore import Project, Library, Package
from codeontology.rdfization.python3.extract.parser import Parser



class Individuals:
    # !!! using automatically generated IRIs for individuals, could be useful to specify a rule for every class?

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

            package.individual.hasSourceCode = package.ast.as_string()
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
    def init_class():
        pass

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
    def init_declaration_statement():
        pass

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
    def init_import_statement(node: Union[astroid.Import, astroid.ImportFrom]):
        node.individual = ontology.ImportStatement()

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


class StructureIndividuals:
    """A collection of methods to create the ontology individuals relatively to the Project structure.

    TODO this will have to be changed, so that packages can be created on the fly from the AST, reached from an import
     node.
    """

    @staticmethod
    def extract_structure_individuals(project: Project):
        """Complete the object properties and data properties of a `Project` object's individual, and recursively
         the properties of its own `Library`es and `Package`s individuals.

        Args:
            project (Project): the `Project` object whose individual has to be completed.

        """
        project.individual = ontology.Project()
        project.individual.hasName = project.name
        # TODO project.individual.hasBuildFile, retrieving the path to the setup file
        # TODO project.individual.hasComment, retrieving the description from the setup file
        for library in (project.libraries | project.dependencies | project.stdlibs):
            StructureIndividuals.__extract_library_individuals(library)
        for library in project.libraries:
            assert library.project
            library.individual.hasProject = library.project.individual
            assert library.individual in project.individual.isProjectOf
        for library in (project.dependencies | project.stdlibs):
            project.individual.hasDependency.append(library.individual)
            assert project.individual in library.individual.isDependencyOf

    @staticmethod
    def __extract_library_individuals(library: Library):
        """Complete the object properties and data properties of a `Library` object's individual, and recursively
         the properties of its own `Package`s individuals.

        Args:
            library (Library): the `Library` object whose individual has to be completed.

        """
        library.individual = ontology.Library()
        library.individual.hasName = library.name
        if library.project:
            library.individual.hasProject = library.project.individual

        for package in library.root_package.get_packages():
            StructureIndividuals.__extract_package_individuals(package)
            assert package.individual in library.individual.isLibraryOf

    @staticmethod
    def __extract_package_individuals(package: Package):
        """Complete the object properties and data properties of a `Package` object's individual.

        Args:
            package (Package): the `Package` object whose individual has to be completed.

        """


class CodeIndividuals:
    """A collection of methods to create the ontology individuals relatively to the Project source code."""



    @staticmethod
    def build_class_individual(node: astroid.ClassDef) -> ontology.Class:
        class_individual = ontology.Class()
        package = node.root().package

        class_individual.hasSimpleName = node.name

        # CAVEAT now assuming no classes are defined inside functions/methods, it's false, but I'm in a hurry
        scope_hierarchy_names = []
        scope = node.scope()
        while not isinstance(scope, astroid.nodes.Module):
            scope_hierarchy_names.insert(0, scope.name)
            scope = scope.parent.scope()
        class_individual.hasFullyQualifiedName = f"{package.full_name}.{'.'.join(scope_hierarchy_names)}"

        class_individual.hasPackage = package.individual
        assert class_individual in package.individual.isPackageOf

        if node.doc_node:
            docstring = Parser.parse_comment(node.doc_node.value)
            short_description = docstring.short_description if docstring.short_description else ""
            class_individual.hasDocumentation.append(short_description)

        class_individual.hasSourceCode = node.as_string()

        # TODO ancestors may be defined in other packages, not yet doable until 'retrieve_or_create' is implemented
        # for ancestor in node.ancestors(recurs=False):
        #     class_individual.extends =

        return class_individual

    @staticmethod
    def build_constructor_individual(node: astroid.FunctionDef) -> ontology.Constructor:
        constructor_individual = ontology.Constructor()

        class_node = node.parent.scope()
        assert isinstance(class_node, astroid.ClassDef)
        assert getattr(class_node, "class_individual", "<unmatched>") != "<unmatched>"
        class_individual = getattr(class_node, "class_individual")

        class_individual.hasConstructor.append(constructor_individual)
        assert constructor_individual.isConstructorOf == class_individual

        constructor_individual.hasName = node.name

        if node.doc_node:
            docstring = Parser.parse_comment(node.doc_node.value)
            short_description = docstring.short_description if docstring.short_description else ""
            constructor_individual.hasDocumentation.append(short_description)

        return constructor_individual

    @staticmethod
    def build_method_individual(node: astroid.FunctionDef) -> ontology.Method:
        method_individual = ontology.Method()

        class_node = node.parent.scope()
        assert isinstance(class_node, astroid.ClassDef)
        assert getattr(class_node, "class_individual", "<unmatched>") != "<unmatched>"
        class_individual = getattr(class_node, "class_individual")

        class_individual.hasMethod.append(method_individual)
        assert method_individual.isMethodOf == class_individual

        method_individual.hasName = node.name

        if node.doc_node:
            docstring = Parser.parse_comment(node.doc_node.value)
            short_description = docstring.short_description if docstring.short_description else ""
            method_individual.hasDocumentation.append(short_description)

        return method_individual

    @staticmethod
    def build_parameters_individual(node: astroid.Arguments) -> List[ontology.Parameter]:
        parameters_individuals = []

        method_constructor_class = node.scope()
        assert isinstance(method_constructor_class, astroid.FunctionDef)
        if method_constructor_class.is_method() and method_constructor_class.name == "__init__":
            assert getattr(method_constructor_class, "constructor_individual", "<unmatched>") != "<unmatched>"
            method_constructor_individual = getattr(method_constructor_class, "constructor_individual")
        else:
            assert method_constructor_class.is_method()
            assert getattr(method_constructor_class, "method_individual", "<unmatched>") != "<unmatched>"
            method_constructor_individual = getattr(method_constructor_class, "method_individual")

        for arg in node.args:
            parameter_individual = ontology.Parameter()

            parameter_individual.hasName = arg.name

            parameter_individual.isParameterOf = method_constructor_individual
            assert parameter_individual in method_constructor_individual.hasParameter

        return parameters_individuals

    @staticmethod
    def retrieve_or_create(node: astroid.NodeNG, attribute_name: str, creation_args_dict: dict = None):
        # IDEA using a function that retrieve an individual if already existent, or creates it if it is not, is the
        #  key to being able to create individual from a structure that is not linear, such the linked ASTs (because
        #  of the connections introduced through import statements) that we access linearly (AST by AST), bringing
        #  us in the condition in which we could face more than one time the same concept.
        individual = getattr(node, attribute_name, "<unmatched>")
        if individual == "<unmatched>":
            if not creation_args_dict:
                creation_args_dict = dict()
            builder_fun = getattr(CodeIndividuals, f"build_{attribute_name}")
            individual = builder_fun(node, **creation_args_dict)
        return individual


class NonExistent:
    pass
