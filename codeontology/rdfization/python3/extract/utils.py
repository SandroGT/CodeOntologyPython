"""Support generic functions for the extraction."""

from typing import Set

import astroid


def get_parent_node(
        node: astroid.NodeNG,
        parent_types: Set[astroid.nodes.NodeNG] = None
) -> astroid.nodes.NodeNG:
    """Gets the first parent node of the specified type that contains the input node.

    Args:
        node (astroid.NodeNG): the input node.
        parent_types(Set[astroid.nodes.LocalsDictNodeNG]): the types of scopes to search for; by default it will be
         the set `{astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}`.

    Returns:
        astroid.nodes.LocalsDictNodeNG: a scope node containing the input node in its descendants.

    Notes:
        I know there is the `astroid.NodeNG.scope()` method, but I needed these specific types of scopes

    """
    if parent_types is None:
        parent_types = {astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}

    while type(node) not in parent_types:
        node = node.parent

    assert node is not None
    return node
