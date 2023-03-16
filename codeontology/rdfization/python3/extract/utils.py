"""Support generic functions for the extraction."""

from typing import Set, Type, Union

import astroid

BLOCK_NODES: Set = {astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef, astroid.For,
                    astroid.While, astroid.If, astroid.TryExcept, astroid.TryFinally, astroid.ExceptHandler,
                    astroid.With}


def get_parent_node(
        node: astroid.NodeNG,
        parent_types: Set[Type[astroid.NodeNG]] = None,
        include_node: bool = False
) -> Union[astroid.NodeNG, None]:
    """Gets the first parent node of the specified type that contains the input node.

    Args:
        node (astroid.NodeNG): the input node.
        parent_types (Set[astroid.nodes.LocalsDictNodeNG]): the types of parent nodes to search for; by default it will
         be the set `{astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}`.
        include_node (bool): whether to include or not the node itself as a possible result if it already is of a
         compatible type.

    Returns:
        astroid.NodeNG: a scope node containing the input node in its descendants.

    """
    if parent_types is None:
        parent_types = {astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}

    iter_node = node if include_node else node.parent
    while iter_node is not None and type(iter_node) not in parent_types:
        iter_node = iter_node.parent

    return iter_node


def get_stmt(node: astroid.NodeNG):
def get_parent_block_node(node: astroid.NodeNG):
    # Since we modified the next statement of a TryExcept to be its first ExceptHandler, and the next statement of the
    #  last ExceptHandler to be the next statement of the TryExcept, the true parent of an ExceptHandler should be the
    #  parent of the TryExcept
    if type(node) is astroid.ExceptHandler:
        assert type(node.parent) is astroid.TryExcept
        return get_parent_node(node.parent, BLOCK_NODES)
    else:
        return get_parent_node(node, BLOCK_NODES)


    iter_node = node
    while not iter_node.is_statement:
        iter_node = iter_node.parent
    return iter_node
