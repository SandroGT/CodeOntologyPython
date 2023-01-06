"""Tracking functions to link AST nodes and names to their referred AST nodes."""

from typing import Dict, Generator, List, Tuple, Union

import astroid

from codeontology import LOGGER
from codeontology.rdfization.python3.extract.utils import get_parent_node
from codeontology.rdfization.python3.extract.transformer.utils import is_static_method, get_self_ref
from codeontology.utils import pass_on_exception

TRACKING_SCOPES = {astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef}


def track_name_from_local(ref_node: Union[astroid.Name, astroid.AssignName]):
    """TODO"""
    assert type(ref_node) in [astroid.Name, astroid.AssignName]

    scope_modifier = None
    statement = ref_node.statement()
    prev_statement = statement.previous_sibling()
    while prev_statement and scope_modifier is None:
        if type(prev_statement) in [astroid.Global, astroid.Nonlocal] and ref_node.name in prev_statement.names:
            scope_modifier = prev_statement
        prev_statement = prev_statement.previous_sibling()

    matched = None
    if not scope_modifier:
        matched = track_name_from_scope(ref_node.name, get_parent_node(ref_node, TRACKING_SCOPES))
    elif type(scope_modifier) is astroid.Global:
        matched = track_name_from_global(ref_node.name, scope_modifier)
    elif type(scope_modifier) is astroid.Nonlocal:
        matched = track_name_from_nonlocal(ref_node.name, scope_modifier)
    else:
        assert False

    # ??? Redundant
    if matched is None:
        raise NoMatchesException

    return matched


def track_name_from_global(name: str, ref_node: astroid.Global):
    """TODO"""
    assert type(ref_node) is astroid.Global

    matched = track_name_from_scope(name, ref_node.root())

    # ??? Redundant
    if matched is None:
        raise NoMatchesException

    return matched


def track_name_from_nonlocal(name: str, ref_node: astroid.Nonlocal):
    """TODO"""
    assert type(ref_node) is astroid.Nonlocal

    current_scope = get_parent_node(ref_node, TRACKING_SCOPES)
    upper_scope = get_parent_node(current_scope.parent, TRACKING_SCOPES)
    assert type(current_scope) in [astroid.FunctionDef, astroid.AsyncFunctionDef] and \
           type(upper_scope) in [astroid.FunctionDef, astroid.AsyncFunctionDef]

    matched = None
    while type(upper_scope) in [astroid.FunctionDef, astroid.AsyncFunctionDef] and matched is None:
        with pass_on_exception((TrackingFailException,)):
            matched = track_name_from_scope(name, upper_scope, __extend_search=False)
        upper_scope = get_parent_node(upper_scope.parent, TRACKING_SCOPES)

    # Redundant
    if matched is None:
        raise NoMatchesException

    return matched


def track_name_from_scope(
        name: str,
        scope_node: astroid.nodes.LocalsDictNodeNG,
        __extend_search: bool = True,
        __trace: Dict[str, List[str]] = None
):
    """TODO"""

    def track_is_cycling(
            name: str,
            scope: astroid.nodes.LocalsDictNodeNG,
            trace: Dict[str, List[astroid.nodes.LocalsDictNodeNG]]
    ) -> bool:
        """TODO"""
        cycling = False
        if trace.get(name, None) is not None:
            previously_searched_scopes = trace.get(name, [])
            cycling = scope in previously_searched_scopes
        return cycling

    def track_update_trace(
            name: str,
            scope: astroid.nodes.LocalsDictNodeNG,
            trace: Dict[str, List[astroid.nodes.LocalsDictNodeNG]]
    ):
        """TODO"""
        if trace.get(name, None) is None:
            trace[name] = [scope]
        else:
            trace[name].append(scope)

    assert isinstance(scope_node, astroid.nodes.LocalsDictNodeNG)

    if __trace is None:
        __trace = dict()
    if track_is_cycling(name, scope_node, __trace):
        raise FoundCyclingException
    track_update_trace(name, scope_node, __trace)

    try:
        matches_scope, matches = scope_node.lookup(name)
    except astroid.AstroidError:
        raise TrackingFailException

    matched = None
    if matches:
        if type(matches[0]) is astroid.Import:
            matched = track_name_from_import(name, matches[0])
        elif type(matches[0]) is astroid.ImportFrom:
            matched = track_name_from_import_from(name, matches[0], __trace=__trace)
        else:
            matched = matches[0]
    elif __extend_search and not type(scope_node) is astroid.Module:
        # If match failed locally, try upward scopes
        with pass_on_exception((TrackingFailException,)):
            matched = track_name_from_scope(name, get_parent_node(scope_node.parent, TRACKING_SCOPES), __trace=__trace)
    elif __extend_search:
        # If there are no more upwards scopes, try global wildcard imports
        assert type(scope_node) is astroid.Module
        with pass_on_exception((TrackingFailException,)):
            matched = track_name_from_wildcards(name, scope_node, __trace=__trace)

    if matched is None or \
            type(matched) not in [astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef,
                            astroid.AssignName, astroid.AssignAttr]:
        raise NoMatchesException

    return matched


def track_name_from_import(name: str, ref_node: astroid.Import):
    """TODO"""
    assert type(ref_node) is astroid.Import

    matched = None
    for name_, alias_ in ref_node.names:
        to_cmp = alias_ if alias_ else name_
        if to_cmp.startswith(name):
            try:
                matched = ref_node.do_import_module(name_)
                break
            except astroid.AstroidImportError:
                raise TrackingFailException

    if matched is None:
        raise NoMatchesException

    assert type(matched) is astroid.Module
    return matched


def track_name_from_import_from(
        name: str,
        ref_node: astroid.ImportFrom,
        __trace: Dict[str, List[astroid.nodes.LocalsDictNodeNG]] = None
):
    """TODO"""
    assert type(ref_node) is astroid.ImportFrom

    try:
        module = ref_node.do_import_module(ref_node.modname)
    except astroid.AstroidImportError:
        raise TrackingFailException
    assert module

    matched = None
    if ref_node.names[0][0] == "*":
        try:
            matched = ref_node.do_import_module(f"{ref_node.modname}.{name}")
        except astroid.AstroidImportError:
            matched = track_name_from_scope(name, module, __trace=__trace)
    else:
        for name_, alias_ in ref_node.names:
            to_cmp = alias_ if alias_ else name_
            if to_cmp.startswith(name):
                try:
                    matched = ref_node.do_import_module(f"{ref_node.modname}.{name_}")
                except astroid.AstroidImportError:
                    matched = track_name_from_scope(name_, module, __trace=__trace)
                break

    if matched is None or \
            type(matched) not in [astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef,
                            astroid.AssignName, astroid.AssignAttr]:
        raise NoMatchesException

    return matched


def track_name_from_wildcards(name: str, module_node: astroid.Module, __trace: Dict[str, List[str]]):
    """TODO"""
    assert type(module_node) is astroid.Module

    wildcard_imports = []
    for child in module_node.get_children():
        if type(child) is astroid.ImportFrom and child.names[0][0] == "*":
            # Insert in reverse because later imports override earlier ones
            wildcard_imports.insert(0, child)

    matched = None
    for import_node in wildcard_imports:
        matched = track_name_from_import_from(name, import_node, __trace=__trace)
        if matched is not None:
            break

    if matched is None or \
            type(matched) not in [astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef,
                            astroid.AssignName, astroid.AssignAttr]:
        raise NoMatchesException

    return matched


def track_attr_from_local(
        ref_node: Union[astroid.Attribute, astroid.AssignAttr],
        __trace: Dict[str, List[str]] = None
):
    """TODO"""
    assert type(ref_node) in [astroid.Attribute, astroid.AssignAttr]

    # In case of something like `a.b.c` we find a first node of type `Attribute` for `c`. `c` has a child for `b`, and
    #  `b` has a child for `a`. Visiting the children we can build the list `[a, b, c]`
    attr_list = []
    children = [ref_node]
    while children:
        assert len(children) == 1
        child = children[0]
        if type(child) in [astroid.Attribute, astroid.AssignAttr]:
            attr_list.insert(0, child.attrname)
        elif type(child) is astroid.Name:
            assert not list(child.get_children())
            attr_list.insert(0, child.name)
        else:
            # !!! TODO One of the children may be a `Call` or some `Subscript`, as we may be accessing to an attribute
            #  of some object that is not a simple `Name` or `Attribute`, but a call to a method/function, or an access
            #  to an element of a set/list/dictionary... In this case we should resolve the type of the `Call` or
            #  `Subscript` (or whatever else we may face) to properly link the name we are tracking to the field or
            #  method it represent.
            #  An example of this clause may be `my_list[0].attribute` or `my_function().attribute`: we cannot link
            #  `attribute` to something without knowing what `my_list[0]` or `my_function()` are, because we don't know
            #  in which contexts to look for `attribute`. Inference is a must!
            raise NotPredictedClauseException
        children = list(child.get_children())

    return track_attr_list_from_scope(attr_list, get_parent_node(ref_node, TRACKING_SCOPES), __trace=__trace)


def track_attr_list_from_scope(
        attr_list:List[str],
        scope_node: astroid.nodes.LocalsDictNodeNG,
        __trace: Dict[str, List[str]] = None
):
    """TODO"""
    matched = None
    _ref_node = scope_node
    # !!! TODO If we are in a non-static method, the first parameter (typically `self`) it's not just a parameter, but a
    #  reference to the instance of the class itself! We should consider this!
    for i in range(0, len(attr_list)):
        # If attributes are `[a, b, c]`, track `a`, then `b`, then `c`
        for j in range(i, -1, -1):
            # When tracking for `c`, you may not find it alone, so search for `c`, then `b.c`, then `a.b.c` on its whole
            name = '.'.join(attr_list[j:i + 1])
            matched = None
            with pass_on_exception((TrackingFailException,)):
                matched = track_name_from_scope(name, get_parent_node(_ref_node, TRACKING_SCOPES))
            if matched is not None:
                break
        if matched is None:
            raise NoMatchesException
        else:
            _ref_node = matched

    if matched is None:
        raise NoMatchesException

    return matched


def track_type_name_from_scope(
        name: str,
        scope_node: astroid.nodes.LocalsDictNodeNG,
        __trace: Dict[str, List[str]] = None
):
    """TODO"""
    assert isinstance(scope_node, astroid.nodes.LocalsDictNodeNG)

    if __trace is None:
        __trace = dict()
    matched = track_attr_list_from_scope(name.split("."), scope_node, __trace=__trace)

    max_iterations = 10
    iterations = 0
    while matched is not None and type(matched) is astroid.AssignName:
        # We have got an alias: the class is assigned here and the real type is on the right side, that we should solve.
        # NOTE this is typical of the `typing` module, whereas many type names are aliases of other classes; for
        #  example `Tuple` is an alias for `_TupleType` inside that module.
        if type(matched.parent) is astroid.Assign:
            children = list(matched.parent.get_children())
            assert len(children) == 2

            right_side = children[1]
            if type(right_side) in [astroid.Call, astroid.Name, astroid.Attribute]:
                if type(right_side) is astroid.Call:
                    right_side = list(right_side.get_children())[0]
                    assert type(right_side) in [astroid.Name, astroid.Attribute]
                if type(right_side) is astroid.Name:
                    new_matched = track_name_from_local(right_side)
                elif type(right_side) is astroid.Attribute:
                    new_matched = track_attr_from_local(right_side)
                else:
                    assert False
                if matched is new_matched:
                    raise FoundCyclingException
                else:
                    matched = new_matched
            else:
                matched = resolve_value(right_side)
        else:
            matched = None

        iterations += 1
        if iterations >= max_iterations:
            raise MaxIterationsException

    if matched is None or type(matched) is not astroid.ClassDef:
        raise NoMatchesException

    return matched


def resolve_value(value_node: astroid.NodeNG) -> astroid.ClassDef:
    """Gets a reference to the AST node representing the type of the value.

    Args:
        value_node (astroid.NodeNG): a node representing an expression or a constant.

    Returns:
        astroid.ClassDef: the reference to the class defining the inferred type of the value, or `None`, if it is not
         possible to resolve the value type.

    """
    type_ = None
    with pass_on_exception((astroid.AstroidError, TrackingFailException,)):
        i = 0
        max_inferences = 3
        inferred_value = astroid.Uninferable
        inferred_generator = value_node.infer()
        while i < max_inferences and inferred_value in [astroid.Uninferable, astroid.Instance]:
            try:
                inferred_value = next(inferred_generator)
                i += 1
            except RecursionError:
                i += 1
            except StopIteration:
                break
        if inferred_value not in [astroid.Uninferable, astroid.Instance]:
            if type(inferred_value) is astroid.ClassDef:
                type_ = inferred_value
            else:
                # ??? May need more `elif` clauses
                str_type_list = inferred_value.pytype().split(".")
                str_type_module = str_type_list[0]
                if str_type_module in ['', 'builtins', value_node.root().name]:
                    str_type = ".".join(str_type_list[1:])  # Skip the module info
                else:
                    # Keep everything, since the module is in an outside scope and we need it for tracking
                    str_type = ".".join(str_type_list)
                with pass_on_exception((TrackingFailException,)):
                    type_ = track_type_name_from_scope(str_type, get_parent_node(value_node))

    if type(type_) is not astroid.ClassDef:
        type_ = None

    return type_


def resolve_annotation(annotation_node: astroid.NodeNG) -> Union[str, List, Tuple, None]:
    """Gets a reference to the AST nodes representing the types to which an annotation may be referring to, whenever
     possible.

    Annotations may refer to a single simple type, or combination of types. The information about the types given by the
     annotation is structured this way:
      A) a reference to a single AST Class node is used to directly represent a type;
      B) a list is used to represent equivalent types (unions in type annotations), and every element of the list can
          recursively be a reference to an AST Class node, a list or a tuple;
      C) a tuple is used to represent parameterized types, such that the first element of the tuple is an AST
          Class node directly representing a type, while every following element define its parameterization, and can
          recursively be a reference to an AST Class node, a list or a tuple;

    Args:
        annotation_node (astroid.NodeNG): the node defining the annotation.

    Returns:
        The structured representation of the type to which the annotation may be referring to, in the form of structured
         references to AST Class nodes, or `None`, if it is not possible to resolve the annotation.

    """
    class Nothing:
        """Used during structuring to distinguish no results from `None`."""
        pass

    class Union(list):
        """Used during structuring to distinguish a list from a list of equivalent types. Not needed afters the class
         name resolution."""
        pass

    def structure_annotation(ann_node: astroid.NodeNG) -> ...:
        """Structures the information about types as described in the parent function, but uses 'Class' names instead of
         the references to the AST nodes in which the respective classes are declared.

        Examples:
            The following annotation:
                Tuple[List[str], Tuple[int, int] | float | Exception] | List
            Would be converted to:
                [("Tuple", ("List", "str"), [("Tuple", "int", "int"), "float", "Exception"]), "List"]
            This is obviously an overly complex and unusual annotation, but it should serve as a clear example.
        """
        # Default value, in case it is not possible to resolve the annotation with the defined cases
        structured_ann = Nothing

        # Explore the cases that may constitute an annotation

        # A) Single types (base case)
        if type(ann_node) is astroid.Name:
            # Reference to a non-nested class, such as 'str'
            structured_ann = ann_node.name
        elif type(ann_node) is astroid.Attribute:
            # Reference to a class contained within another class or package, such as 'os.Path'.
            nested_names = []
            nested_annotation_node = ann_node
            while type(nested_annotation_node) is astroid.Attribute:
                nested_names.insert(0, nested_annotation_node.attrname)
                nested_annotation_node = nested_annotation_node.expr
            assert type(nested_annotation_node) is astroid.Name
            nested_names.insert(0, nested_annotation_node.name)
            structured_ann = ".".join(nested_names)
        elif type(ann_node) is astroid.Const:
            if ann_node.value is None:
                # When used in typing, `None` is considered equivalent to its type `NoneType`
                structured_ann = "NoneType"
            elif type(ann_node.value) is type(Ellipsis):
                # Use of '...' in the annotation, meaning 'any value' in a type hinting context
                structured_ann = "Any"
            elif type(ann_node.value) is str:
                # Use of a stringified annotations, such as `"List[str]"` instead of `List[str]`, but just skip them for
                #  now and treat them like unresolvable cases
                pass

        # B) Equivalent types (recursive step)
        elif type(ann_node) is astroid.BinOp:
            # Use of a 'type union', such as 'int | List[float]'
            equivalent_types = []
            bin_op_node = ann_node
            while type(bin_op_node) is astroid.BinOp:
                assert bin_op_node.op == "|"  # The only supported operator in annotations
                equivalent_types.insert(0, bin_op_node.right)
                bin_op_node = bin_op_node.left
            equivalent_types.insert(0, bin_op_node)
            structured_ann = Union([structure_annotation(ann_node) for ann_node in equivalent_types])
        # TODO should also look for uses of `typing.Union`

        # C) Parameterized types (recursive step)
        elif type(ann_node) is astroid.Subscript:
            # Definition of a parameterized type, such as 'Tuple[...]'
            base_type = [structure_annotation(ann_node.value)]
            base_type_param = structure_annotation(ann_node.slice)
            if base_type_param is not Nothing:
                if type(base_type_param) in [str, Union]:
                    base_type_param = [base_type_param]
                else:
                    assert type(base_type_param) in [list, tuple]
                    base_type_param = list(base_type_param)
                structured_ann = tuple(base_type + base_type_param)
            else:
                structured_ann = None
        elif type(ann_node) in [astroid.List, astroid.Tuple]:
            # Definition of the parameterization of a type with possible multiple values, such as '...[int, float]'
            assert type(ann_node.elts) is list
            structured_ann = [structure_annotation(e) for e in ann_node.elts]

        return structured_ann

    def resolve_class_names(ann_node: astroid.NodeNG, structured_ann: ...) -> ...:
        """Resolves the names of the classes in a structured annotation, replacing them with the reference to the
         respective AST Class nodes.
        """
        # Default value, in case it is not possible to resolve the names
        match_type = None

        # Explore the cases that may constitute the structured annotation
        if structured_ann is Nothing:
            # Absence of the structured annotation info, no matches with any type
            match_type = None

        # A) Single types (base case)
        elif type(structured_ann) is str:
            with pass_on_exception((TrackingFailException,)):
                match_type = track_type_name_from_scope(structured_ann, get_parent_node(ann_node, TRACKING_SCOPES))

        # B) Equivalent types (recursive step)
        elif type(structured_ann) in [list, Union]:
            match_type = [resolve_class_names(ann_node, a) for a in structured_ann]

        # C) Parameterized types (recursive step)
        elif type(structured_ann) is tuple:
            match_type = tuple([resolve_class_names(ann_node, a) for a in structured_ann])

        return match_type

    structured_annotation = None
    with pass_on_exception((astroid.AstroidError, TrackingFailException,)):
        structured_annotation = structure_annotation(annotation_node)

    matched_type = resolve_class_names(annotation_node, structured_annotation)

    return matched_type


def track_fields(class_node: astroid.ClassDef) -> Generator[Tuple, None, None]:
    """Gets the ordered list of assignments that are expected and may define some fields. Each assignment of interest is
     represented by a tuple of:
      (t) `target` is the name, or list of names (for tuple assignments) that are being instantiated;
      (a) `annotation` is the optional annotation that may be tagging the assignment;
      (v) `value` is the expression assigned to the target, and may be missing for 'annotation assignments';
      (n) `node` is the node related to the assignment.
    As mentioned, the list is ordered, in the same order as the interpreter executes the assignments, so that if two
     identical targets occur, the interpreter can simply overwrite what was set by the previous one without regret.
    An assigment correctly defines a field only when it also assigns a value ('annotation assignments' are not enough).

    Args:
        class_node (astroid.ClassDef): a node representing a class definition and body.

    Returns:
        Generator[Tuple, None, None]: the generator of the ordered list of assigment tuples.

    """
    def get_tavn_list_class(cls_node: astroid.ClassDef) -> Generator[Tuple, None, None]:
        """1) Gets the assignments tuples '(target, annotation, value, node,)' from a class body."""
        assert type(cls_node) is astroid.ClassDef

        # Find the names which refer to global variables to properly skip their assignments: they are not attributes
        global_names = set()
        for cls_body_node in cls_node.get_children():
            if type(cls_body_node) is astroid.Global:
                for name in cls_body_node.names:
                    global_names.add(name)

        # Scroll through the 'assignment nodes' in the class body, to find the names names that refer to fields
        #  (assignments) or potential fields (annotation assignments)
        for cls_body_node in cls_node.get_children():
            if type(cls_body_node) is astroid.Assign:
                # Assignment with no annotation, such as: `<target_1> = <target_2> = ... = <expression>`
                for target in cls_body_node.targets:
                    if type(target) is astroid.Tuple:
                        # Tuple assignment, so `<target_x>` is something like `<element_1, element_2, ...>`
                        for element in target.elts:
                            assert type(element) in [astroid.AssignName, astroid.AssignAttr]
                            if type(element) is astroid.AssignName and element.name not in global_names:
                                # `name` is referencing a class attribute
                                # !!! We set the value of `(v)` to `None` because the only value we know is
                                #  `cls_body_node.value`, which indicates the value of the entire tuple, and it is not
                                #  easily correlated to its individual elements.
                                yield element.name, None, None, element
                            elif type(element, astroid.AssignAttr) or element.name in global_names:
                                # `name` is not referencing a class attribute
                                pass
                            else:
                                assert False
                    elif type(target) is astroid.AssignName:
                        # Single named target, so `<target_x>` is something like `<element_1>`
                        if target.name not in global_names:
                            # `name` is referencing a class attribute, yield the tuple
                            yield target.name, None, cls_body_node.value, target,
                    elif type(target) is astroid.AssignAttr:
                        # Single named attribute target, so `<target_x>` is something like `<object.attr>`, and cannot
                        #  be a class attribute
                        pass
                    elif type(target) is astroid.Subscript:
                        # We are assigning to target using square brackets, so to an inside element of the target,
                        #  that tells us not much about attributes
                        pass
                    else:
                        assert False
            elif type(cls_body_node) is astroid.AnnAssign:
                # Assignment with annotation, such as: `<target>: <annotation> = <expression>`
                # Chained assignment (`<t_1> = <t_2> = ... = <expr>`) and tuple assignment (`<n_1, n_2, ...> = <expr>`)
                #  cannot occur in annotation assignments
                target = cls_body_node.target
                assert type(target) in [astroid.AssignName, astroid.AssignAttr]
                if type(target) is astroid.AssignName:
                    if target.name not in global_names:
                        # `name` is referencing a class attribute, yield the tuple
                        yield target.name, cls_body_node.annotation, cls_body_node.value, target,
                elif type(target) is astroid.AssignAttr:
                    # Single named attribute target, so <target> is something like <object.attr>, and cannot be a class
                    #  attribute
                    pass
                else:
                    assert False

    def get_tavn_list_constructor(cls_node: astroid.ClassDef, ctor_node: astroid.FunctionDef) \
            -> Generator[Tuple, None, None]:
        """2) Gets the assignments tuples '(target, annotation, value, node,)' from a constructor body."""
        assert type(cls_node) is astroid.ClassDef and type(ctor_node) is astroid.FunctionDef and ctor_node.name == "__init__"

        if not ctor_node.body or is_static_method(ctor_node):
            # If there is no body, there is no `__init__` declaration nor inheritance from other ancestors constructors,
            #  so no attributes can be declared here.
            # Furthermore, if for some bizarre reason the `__init__` constructor has been tagged as 'static', there is
            #  no self-reference to the object, thus no attributes can be declared here either.
            pass
        else:
            # Find the name of the parameter used for self-reference
            self_ref = get_self_ref(ctor_node)
            # You can define an __init__ method with no arguments (so no self-reference) since it is syntactically
            #  possible, even though you can actually never call it at runtime, because the object from which the method
            #  is called would be automatically passed as first argument of the call, and raise the error:
            #  `__init__() takes 0 positional arguments but 1 was given`
            # Anyway, since it is syntactically possible we do not raise any Exception, just yield nothing. We do not
            #  except to reach this case anyway.
            if not self_ref:
                LOGGER.debug(f"Found an '__init__()' with no self-reference in '{ctor_node.root().file}'.")
                return

            # Check the body for self-assignments and calls to ancestor constructors
            for ctor_body_node in ctor_node.body:

                # - Self-assignments check
                if type(ctor_body_node) is astroid.Assign:
                    # Assignment with no annotation, such as: `<target_1> = <target_2> = ... = <expression>`
                    for target in ctor_body_node.targets:
                        if type(target) is astroid.Tuple:
                            # Tuple assignment, so `<target_x>` is something like `<element_1, element_2, ...>`
                            for element in target.elts:
                                assert type(element) in [astroid.AssignName, astroid.AssignAttr, astroid.Starred,
                                                         astroid.Subscript]
                                if type(element) is astroid.AssignAttr:
                                    assert type(element.expr) is astroid.Name
                                if type(element) is astroid.AssignAttr and element.expr.name == self_ref:
                                    # `name` is referencing a class attribute through self-reference
                                    # !!! We set the value of `(v)` to `None` because the only value we know is
                                    #  `cls_body_node.value`, which indicates the value of the entire tuple, and it is
                                    #  not easily correlated to its individual elements.
                                    yield element.attrname, None, None, element
                                else:
                                    # `name` is not referencing a class attribute
                                    pass
                        elif type(target) is astroid.AssignAttr:
                            # Single named target, so `<target_x>` is something like `<object.attr>`, and if `object`
                            #  is a self-reference then it is a class attribute assignment
                            if type(target.expr) is astroid.Name and target.expr.name == self_ref:
                                yield target.attrname, None, ctor_body_node.value, target,
                        elif type(target) is astroid.AssignName:
                            # Single named attribute target, so `<target_x>` is something like `<element_1>`, and cannot
                            #  be a class attribute without self-reference
                            pass
                        elif type(target) is astroid.Subscript:
                            # We are assigning to target using square brackets, so to an inside element of the target,
                            #  that tells us not much about attributes
                            pass
                        else:
                            assert False
                elif type(ctor_body_node) is astroid.AnnAssign:
                    # Assignment with annotation, such as: `<target>: <annotation> = <expression>`
                    # Chained assignment (`<t_1> = <t_2> = ... = <expr>`) and tuple assignment
                    #  (`<n_1, n_2, ...> = <expr>`) cannot occur in annotation assignments
                    target = ctor_body_node.target
                    if type(target) is astroid.AssignAttr:
                        assert type(target.expr) is astroid.Name
                        if target.expr.name == self_ref:
                            # `name` is referencing a class attribute, yield the tuple
                            yield target.attrname, ctor_body_node.annotation, ctor_body_node.value, target,
                    elif type(target) is astroid.AssignName:
                        # Single named attribute target, so `<target_x>` is something like `<element_1>`, and cannot
                        #  be a class attribute without self-reference
                        pass
                    else:
                        assert False

                # - Constructor calls check
                elif type(ctor_body_node) is astroid.Expr and type(ctor_body_node.value) is astroid.Call:
                    # Constructor calls (`__init__` calls) can be done in two ways:
                    #  1) Using `super()` to get a object reference to the first matching constructor in the MRO, as in
                    #      `super().__init__(<params>)`;
                    #  2) Using the explicit name of the class to choose a constructor from a specific ancestor, and
                    #      passing the self-reference object as in `AncestorClass.__init__(<self-ref>, <params>)`
                    call_func, call_params = ctor_body_node.value.func, ctor_body_node.value.args
                    if type(call_func) is astroid.Attribute and call_func.attrname == "__init__":
                        # Check case 1)
                        if type(call_func.expr) is astroid.Call:
                            init_caller = getattr(call_func.expr.func, "name", None)
                            if init_caller and init_caller == "super":
                                init_found = False
                                for ancestor_node in cls_node.mro()[1:]:  # First in MRO is the parent class itself
                                    for ancestor_method_node in ancestor_node.methods():
                                        if ancestor_method_node.name == "__init__":
                                            yield from get_tavn_list_constructor(ancestor_node, ancestor_method_node)
                                            init_found = True  # No overload in Python, so just one constructor
                                            break
                                    if init_found:
                                        break
                        # Check case 2)
                        if type(call_func.expr) is astroid.Name:
                            ancestor_name = call_func.expr.name
                            ancestor_node = None
                            for _ancestor in cls_node.ancestors(recurs=True):
                                if _ancestor.name == ancestor_name:
                                    ancestor_node = _ancestor
                                    break
                            if ancestor_node:
                                for ancestor_method_node in ancestor_node.methods():
                                    if ancestor_method_node.name == "__init__":
                                        yield from get_tavn_list_constructor(ancestor_node, ancestor_method_node)
                                        break  # No overload in Python, so just one constructor

    assert type(class_node) is astroid.ClassDef
    # The order of execution of the assignments that may define fields is the following:
    #  1) the assignments in the class body, from ancestors too (not annotation assignments though);
    #  2) the assignments in the constructor/s, that are twofold
    #    2.a) the assignments from the explicit constructor `__init__`, if defined;
    #    2.b) the assignments from the inherited constructors according to the MRO, if no explicit `__init__` is defined
    #          or a call to ancestor constructors is explicitly performed

    # 1)
    for ancestor in reversed(list(class_node.ancestors())):
        yield from get_tavn_list_class(ancestor)
    yield from get_tavn_list_class(class_node)

    # 2)
    for method_node in class_node.methods():
        if method_node.name == "__init__":
            yield from get_tavn_list_constructor(class_node, method_node)
            break  # No overload in Python, so just one constructor


class TrackingFailException(Exception):
    pass


class NoMatchesException(TrackingFailException):
    pass


class NotPredictedClauseException(TrackingFailException):
    pass


class FoundCyclingException(TrackingFailException):
    pass


class MaxIterationsException(TrackingFailException):
    pass
