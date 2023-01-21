"""Support generic functions for the extraction."""

from typing import Set, Type, Union

import astroid


def get_parent_node(
        node: astroid.NodeNG,
        parent_types: Set[Type[astroid.NodeNG]] = None
) -> Union[astroid.NodeNG, None]:
    """Gets the first parent node of the specified type that contains the input node.

    Args:
        node (astroid.NodeNG): the input node.
        parent_types(Set[astroid.nodes.LocalsDictNodeNG]): the types of parent nodes to search for; by default it will
         be the set `{astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}`.

    Returns:
        astroid.NodeNG: a scope node containing the input node in its descendants.

    """
    if parent_types is None:
        parent_types = {astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}

    iter_node = node.parent
    while iter_node is not None and type(iter_node) not in parent_types:
        iter_node = iter_node.parent

    return iter_node
