"""Support generic functions for the transformations to apply on AST nodes."""

from typing import Set, Union

import astroid


def get_scope_node(
        node: astroid.NodeNG,
        scope_types: Set[astroid.nodes.LocalsDictNodeNG] = None
) -> astroid.nodes.LocalsDictNodeNG:
    """Gets the first scope node of the specified type that contains the input node.

    Args:
        node (astroid.NodeNG): the input node.
        scope_types(Set[astroid.nodes.LocalsDictNodeNG]): the types of scopes to search for; by default it will be
         the set `{astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}`.

    Returns:
        astroid.nodes.LocalsDictNodeNG: a scope node containing the input node in its descendants.

    Notes:
        I know there is the `astroid.NodeNG.scope()` method, but I needed these specific types of scopes

    """
    if scope_types is None:
        scope_types = {astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}

    while type(node) not in scope_types:
        node = node.parent

    assert node and isinstance(node, astroid.nodes.LocalsDictNodeNG)
    return node


def is_static_method(func_node: Union[astroid.FunctionDef, astroid.AsyncFunctionDef]) -> bool:
    """Tells if a method is a static method by looking at its decorators. A function is always considered static.

    Args:
        func_node (Union[astroid.FunctionDef, astroid.AsyncFunctionDef]): a node representing a function/method
         definition and body.

    Returns:
        bool: `True` if the node represents a static method or a function, `False` otherwise.

    """
    assert type(func_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef]
    if func_node.is_method():
        decorators_nodes = func_node.decorators.nodes if func_node.decorators else []
        decorators_names = set()
        for node in decorators_nodes:
            name = ""
            if type(node) is astroid.Name:
                name = node.name
            elif type(node) is astroid.Attribute:
                name = node.attrname
            elif type(node) is astroid.Call:
                if type(node.func) is astroid.Name:
                    name = node.func.name
                elif type(node.func) is astroid.Attribute:
                    name = node.func.attrname
            decorators_names.add(name)
        is_static = "staticmethod" in decorators_names
    else:
        is_static = True
    return is_static


def get_self_ref(fun_node: Union[astroid.FunctionDef, astroid.AsyncFunctionDef]) -> str:
    """Gets the name used to self-reference the object in a method.

    Args:
        fun_node (Union[astroid.FunctionDef, astroid.AsyncFunctionDef]): a node representing a function/method
         definition and body.

    Returns:
        str: the name of the variable representing the object itself within the method, or an empty string if the method
         is static, has no arguments, or it is instead a function.

    Notes:
     Conventionally 'self' is used, but it is not mandatory, so it may be different.

    """
    assert type(fun_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef]

    self_ref = ""
    if not is_static_method(fun_node):
        # In order of definition we have `posonlyargs`, `args`, `vararg`, `kwonlyargs` and `kwarg`; the name used for
        #  self-reference in methods always occupies the first position in the arguments definition.
        if fun_node.args.posonlyargs and len(fun_node.args.posonlyargs) > 0:
            self_ref = fun_node.args.posonlyargs[0].name
        elif fun_node.args.args and len(fun_node.args.args) > 0:
            self_ref = fun_node.args.args[0].name
    return self_ref


class TransformException(Exception):
    pass


class NotPredictedClauseException(TransformException):
    pass
