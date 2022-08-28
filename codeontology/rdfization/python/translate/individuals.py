import sys

import astroid

from codeontology import ontology
from codeontology.rdfization.python.translate.transforms import *


def build_class_individual(node: astroid.ClassDef) -> ontology.Class:
    individual = ontology.Class()

    # Package
    structure_package = getattr(node.root(), "structure_package", "<unmatched>")
    if structure_package != "<unmatched>":
        individual.hasPackage = structure_package.individual
        package_full_name = individual.hasPackage.hasFullyQualifiedName
    else:
        # TODO add a function build_package_individual to create packages individuals and call it here
        package_full_name = node.root().name

    # Class name
    scope = node.scope()
    names = []
    while not isinstance(scope, astroid.Module):
        names.append(scope.name)
        scope = scope.parent.scope()
    individual.hasFullyQualifiedName = package_full_name + "." + ".".join(names)
    individual.hasSimpleName = individual.hasFullyQualifiedName.split(".")[-1]

    # Hierarchy
    for node_ancestor in node.ancestors(recurs=False):
        ancestor_individual = getattr(node_ancestor, "class_individual", "<unmatched>")
        if ancestor_individual == "<unmatched>":
            ancestor_individual = build_class_individual(node_ancestor)
        individual.extends.append(ancestor_individual)
        assert individual in ancestor_individual.hasSubClass

    # Fields

    fields_dict = getattr(node, "fields_dict", "<unmatched>")
    if fields_dict == "<unmatched>":
        transforms_add_class_fields(node)
        fields_dict = getattr(node, "fields_dict", "<unmatched>")
    assert fields_dict != "<unmatched>"
    for field_name in node.fields_dict.keys():
        field_annotation, field_value, field_node = fields_dict[field_name]
        field_individual = getattr(field_node, "field_individual", "<unmatched>")
        if field_individual == "<unmatched>":
            field_individual = build_field_individual(node, field_node)
        assert getattr(field_node, "field_individual", "<unmatched>") != "<unmatched>"

    # Methods

    # Source code
    individual.hasSourceCode = node.as_string()

    # sys.exit(0)

    # Find fields
    return individual


def build_field_individual(class_node, field_node) -> ontology.Field:
    individual = ontology.Field()
    field_node.field_individual = individual
    # TODO continue
