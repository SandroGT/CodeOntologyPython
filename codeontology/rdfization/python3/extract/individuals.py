"""Classes and methods to create and instantiate ontology individuals."""

from typing import List

import astroid

from codeontology.ontology import ontology
from codeontology.rdfization.python3.explore import Project, Library, Package
from codeontology.rdfization.python3.extract.parser import parse_comment


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
        package.individual = ontology.Package()
        package.individual.hasSimpleName = package.simple_name
        package.individual.hasFullyQualifiedName = package.full_name
        package.individual.hasLibrary = package.library.individual


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

        if node.doc_node:
            docstring = parse_comment(node.doc_node.value)
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
            docstring = parse_comment(node.doc_node.value)
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
            docstring = parse_comment(node.doc_node.value)
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
