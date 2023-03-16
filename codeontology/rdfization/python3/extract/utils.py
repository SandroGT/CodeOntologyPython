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


def get_parent_block_node(node: astroid.NodeNG):
    # Since we modified the next statement of a TryExcept to be its first ExceptHandler, and the next statement of the
    #  last ExceptHandler to be the next statement of the TryExcept, the true parent of an ExceptHandler should be the
    #  parent of the TryExcept
    if type(node) is astroid.ExceptHandler:
        assert type(node.parent) is astroid.TryExcept
        return get_parent_node(node.parent, BLOCK_NODES)
    else:
        return get_parent_node(node, BLOCK_NODES)


def get_containing_stmt(node: astroid.NodeNG):
    iter_node = node
    while not iter_node.is_statement:
        iter_node = iter_node.parent
    return iter_node


def get_stmt_info(node: astroid.NodeNG):
    stmt_individual = stmt_attr = None
    if type(node) is astroid.TryFinally:
        if hasattr(node, "stmt_try_individual"):
            stmt_attr = "stmt_try_individual"
            stmt_individual = node.stmt_try_individual
    elif hasattr(node, "stmt_individual"):
        stmt_attr = "stmt_individual"
        stmt_individual = node.stmt_individual

    return stmt_individual, stmt_attr


def get_prev_statement(node: astroid.NodeNG) -> astroid.NodeNG:
    assert node.is_statement
    # `try-except statement`s are treated by astroid single entities, but the try, catch and finally statements are
    # separated concepts in the ontology and we need to cope with that adjusting the statements adjacency by ourselves
    prev_node = node.previous_sibling()
    if type(prev_node) is astroid.TryExcept:
        prev_node = prev_node.handlers[-1]
        assert type(prev_node) is astroid.ExceptHandler
    elif type(node) is astroid.ExceptHandler and prev_node is None:
        assert type(node.parent) is astroid.TryExcept
        prev_node = node.parent

    return prev_node


def get_next_statement(node: astroid.NodeNG) -> astroid.NodeNG:
    assert node.is_statement
    # `try-except statement`s are treated by astroid single entities, but the try, catch and finally statements are
    # separated concepts in the ontology and we need to cope with that adjusting the statements adjacency by ourselves
    next_node = node.next_sibling()
    if type(node) is astroid.TryExcept:
        next_node = node.handlers[0]
        assert type(next_node) is astroid.ExceptHandler
    elif type(node) is astroid.ExceptHandler and next_node is None:
        assert type(node.parent) is astroid.TryExcept
        next_node = node.parent.next_sibling()

    return next_node