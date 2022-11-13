from typing import Generator, Tuple, Union

import astroid


def resolve_annotation(node: ...) -> ...:
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
        node: the node defining the annotation.

    Returns:
        The structured representation of the type to which the annotation may be referring to, in the form of structured
         references to AST Class nodes, or `None`, if its not possible to resolve the annotation.

    """
    def structure_annotation(ann_node: ...) -> ...:
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
        structured_ann = None

        # Explore the cases that may constitute an annotation

        # A) Single types (base case)
        if isinstance(ann_node, astroid.Name):
            # Reference to a non-nested class, such as 'str'
            structured_ann = ann_node.name
        elif isinstance(ann_node, astroid.Attribute):
            # Reference to a class contained within another class or package, such as 'os.Path'.
            nested_names = [ann_node.attrname]
            nested_annotation_node = ann_node.expr
            while isinstance(nested_annotation_node, astroid.Attribute):
                nested_names.insert(0, ann_node.attrname)
                nested_annotation_node = nested_annotation_node.expr
            assert isinstance(nested_annotation_node, astroid.Name)
            nested_names.insert(0, nested_annotation_node.name)
            structured_ann = ".".join(nested_names)
        elif isinstance(ann_node, astroid.Const):
            if isinstance(ann_node.value, type(Ellipsis)):
                # Use of '...' in the annotation, meaning 'any value' in a type hinting context
                structured_ann = "Any"
            elif isinstance(ann_node.value, str):
                # Use of a stringified annotations, such as ' "List[str]" ' instead of ' List[str] ', but just skip
                #  them for now and treat them like unresolvable cases
                pass

        # B) Equivalent types (recursive step)
        elif isinstance(ann_node, astroid.BinOp):
            # Use of a 'type union', such as 'int | List[float]'
            equivalent_types = []
            bin_op_node = ann_node
            while isinstance(bin_op_node, astroid.BinOp):
                assert bin_op_node.op == "|"  # The only supported operator in annotations
                equivalent_types.insert(0, bin_op_node.right)
                bin_op_node = bin_op_node.left
            equivalent_types.insert(0, bin_op_node)
            structured_ann = [structure_annotation(ann_node) for ann_node in equivalent_types]
        # TODO should also look for uses of `typing.Union`

        # C) Parameterized types (recursive step)
        elif isinstance(ann_node, astroid.Subscript):
            # Definition of a parameterized type, such as 'Tuple[...]'
            base_type = [structure_annotation(ann_node.value)]
            base_type_parameterization = structure_annotation(ann_node.slice)
            if isinstance(base_type_parameterization, str):
                base_type_parameterization = [base_type_parameterization]
            else:
                assert isinstance(base_type_parameterization, list) or isinstance(base_type_parameterization, tuple)
                base_type_parameterization = list(base_type_parameterization)
            structured_ann = tuple(base_type + base_type_parameterization)
        elif isinstance(ann_node, astroid.Tuple) or isinstance(ann_node, astroid.List):
            # Definition of the parameterization of a type with possible multiple values, such as '...[int, float]'
            assert isinstance(ann_node.elts, list)
            structured_ann = [structure_annotation(e) for e in ann_node.elts]

        return structured_ann

    def resolve_class_names(ann_node: ..., structured_ann: ...) -> ...:
        """Resolves the names of the classes in a structured annotation, replacing them with the reference to the
         respective AST Class nodes.
        """
        # Default value, in case it is not possible to resolve the names
        match_type = None

        # Explore the cases that may constitute the structured annotation
        if structured_ann is None:
            # Absence of the structured annotation info, no matches with any type
            match_type = None

        # A) Single types (base case)
        elif isinstance(structured_ann, str):
            match_type = lookup_type_by_name(structured_ann, ann_node)

        # B) Equivalent types (recursive step)
        elif isinstance(structured_ann, list):
            match_type = [resolve_class_names(ann_node, a) for a in structured_ann]

        # C) Parameterized types (recursive step)
        elif isinstance(structured_ann, tuple):
            match_type = tuple([resolve_class_names(ann_node, a) for a in structured_ann])

        return match_type

    try:
        matched_type = resolve_class_names(node, structure_annotation(node))
    except Exception:
        matched_type = None

    return matched_type


def lookup_type_by_name(name: str, scope_node: ...) -> astroid.ClassDef:
    """Looks for the reference to the AST node that defines the type specified by the name, using the scope given by
     the passed node.

    Args:
        name (str): the name of the type/class to search for.
        scope_node: the node that defines the scope from which to start the search.

    Returns:
        astroid.ClassDef: the reference to the type/class corresponding to the name.

    Raises:
        Exception: if the lookup operation fails and finds no match.

    """

    def track_type_name(base: str, tail: str, scope_node: ...) -> astroid.ClassDef:
        """Tracks down the type/class related to the specified name, recursively splitting it into `base` and `tail`
         until there are no more trailing names to follow.

        Args:
            base (str): the first part of the name we want to track; for example in '<package>.<wrapper_class>.<type>'
             the base is '<package>'. May also concide with the whole name, if no tail exists.
            tail (str): the trailing parts of the name after `base`; for example in '<package>.<wrapper_class>.<type>'
             the tail is '<wrapper_class>.<type>'. It's `None` at the final step.
            scope_node: the node defining the scope from which to search for the `base`.

        Returns:
            astroid.ClassDef: the reference to the type/class matched to the name.

        Raises:
            Exception: if the tracking operation fails and finds no match.

        """
        assert base is not None

        # Search for the `base` from the scope of the specified `node`
        _, matches = scope_node.lookup(base)

        if matches == () or len(matches) > 1:
            # No match or multiple matches: it is not clear what the string `base` refers to. We have a fail.
            raise Exception(f"No unique match for {base}.")

        # We have one only unique match
        match_node = matches[0]

        # Check the kind of match we have to track down the type
        if isinstance(match_node, astroid.Import) or isinstance(match_node, astroid.ImportFrom):
            match_type = handle_match_Imports(base, tail, match_node)
        elif isinstance(match_node, astroid.ClassDef):
            match_type = handle_match_ClassDef(base, tail, match_node)
        elif isinstance(match_node, astroid.AssignName):
            match_type = utils_handle_type_match_AssignName(base, tail, match_node)
        else:
            raise Exception(f"Unknown type of matched node tracking {base}.")

        return match_type

    def handle_match_Imports(base: str, tail: str, match_node: Union[astroid.Import, astroid.ImportFrom]):
        """The `base` comes from an 'import statement' node.

        We may have statements such as:
         a) >>> import name_1, name_2 as alias_2, name_3, ... (astroid.Import)
         b) >>> from mod_or_pkg import name_1, name_2 as alias_2, name_3, ... (astroid.ImportFrom)
        Our `base` has a match to one of the names or aliases of these imports.
        """
        # In the first case 'a)' the target of the import must start from a module or package, and not a class, so we
        #  must have a `tail` to chase. In case 'b)' names and aliases may also be classes, so the `tail` may be `None`
        if isinstance(match_node, astroid.Import):
            assert tail is not None

        # Search for the module in which to continue the search, and what to search there
        module = None
        new_base = new_tail = None
        if isinstance(match_node, astroid.Import):
            # In case 'a)' we may have multiple packages/modules using an alias that we must resolve
            for imp_name, imp_alias in reversed(
                    match_node.names):  # later imported names override previous ones: reverse
                name_to_cmp = imp_alias if imp_alias else imp_name
                if base == name_to_cmp:
                    module = imp_name
                    tail_list = tail.split(".")
                    new_base = tail_list[0]
                    new_tail = ".".join(tail_list[1:])
                    break
        elif isinstance(match_node, astroid.ImportFrom):
            # In case 'b)' we have a known single package/module from which we may improt all its names (wildcard
            #  import) or just some of them
            module = match_node.modname

            # Wildcard import
            if len(match_node.names) == 1 and match_node.names[0] == ("*", None):
                # Just continue the same search in that module
                new_base = base
                new_tail = tail
            # Non-wildcard import
            else:
                # Check which name we are matching because we must resolve aliases
                for imp_name, imp_alias in reversed(match_node.names):
                    name_to_cmp = imp_alias if imp_alias else imp_name
                    if base == name_to_cmp:
                        new_base = imp_name
                        new_tail = tail
                        break
        else:
            assert False

        # Since `lookup` has found a match, we must have found a name to chase
        assert module is not None and new_base is not None

        # We have a module name from which to continue the search, and this can be followed by a sequence of other
        #  packages/modules/classes in which our type of interest is contained (the last part of the `tail`). We need to
        #  find the deepest package/module in the sequence which is then followed by the classes.
        #
        # As an example:
        #  - `module` could be 'pkg_1';
        #  - `new_base` could be 'pkg_2';
        #  - `new_tail` could be the sequence of a module 'mod_1', a class 'cls_1' and a nested final class 'cls_2'.
        # The fully qualified name of the class of interest ('cls_2') then is 'pkg_1.pkg_2.mod_1.cls_1.cls_2'.
        #                                                                                  |-> the name we want to find!
        fully_qualified_name = ".".join([module, new_base] + ([new_tail] if new_tail else []))
        complete_type_name_list = fully_qualified_name.split(".")
        to_follow_ast = None
        i = 1
        while not to_follow_ast and i < len(complete_type_name_list):
            to_import_mod = ".".join(complete_type_name_list[:-i])
            try:
                to_follow_ast = match_node.do_import_module(to_import_mod)
            except Exception:
                i += 1
        if to_follow_ast:
            j = len(complete_type_name_list) - i
            new_base = ".".join(complete_type_name_list[j:j + 1])
            new_tail = ".".join(complete_type_name_list[j + 1:])
            match_type = track_type_name(new_base, new_tail, to_follow_ast)
        else:
            raise Exception(f"No AST found in which to continue the search for {new_base}, {new_tail}.")

        return match_type

    def handle_match_ClassDef(base: str, tail: str, match_node: astroid.ClassDef):
        """The `base` comes from a 'class definition' node."""
        # If there is a `tail` we have nested classes: just check them recursively
        if tail:
            tail_list = tail.split(".")
            new_base = tail_list[0]
            new_tail = ".".join(tail_list[1:])
            match_type = track_type_name(new_base, new_tail, match_node)
        # If there is no tail, we reached the most inner class: SUCCESS!
        else:
            assert match_node.name == base
            match_type = match_node

        return match_type

    def utils_handle_type_match_AssignName(base: str, tail: str, match_node: astroid.AssignName):
        """The `base` comes from an 'assignment statement' node that creates an alias of our type of interes."""
        assert isinstance(match_node.parent, astroid.Assign)
        # Try to track down the original type/class through the inference tool of `astroid`
        infers = list(match_node.infer())
        # If we have a unique clear result
        if len(infers) == 1 and isinstance(infers[0], astroid.ClassDef):
            match_type = infers[0]
        else:
            raise Exception("Not able to track down the type through the assignment.")

        return match_type

    assert isinstance(name, str) and len(name) > 0
    name_parts = name.split(".")
    name_root = name_parts[0]
    name_tail = ".".join(name_parts[1:])
    return track_type_name(name_root, name_tail, scope_node)


def get_tavn_list(class_node: astroid.ClassDef) -> Generator[Tuple, None, None]:
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
        assert isinstance(cls_node, astroid.ClassDef)

        # Find the names which refer to global variables to properly skip their assignments: they are not attributes
        global_names = set()
        for cls_body_node in cls_node.get_children():
            if isinstance(cls_body_node, astroid.Global):
                for name in cls_body_node.names:
                    global_names.add(name)

        # Scroll through the 'assignment nodes' in the class body, to find the names names that refer to fields
        #  (assignments) or potential fields (annotation assignments)
        for cls_body_node in cls_node.get_children():
            if isinstance(cls_body_node, astroid.Assign):
                # Assignment with no annotation, such as: `<target_1> = <target_2> = ... = <expression>`
                for target in cls_body_node.targets:
                    assert isinstance(target, astroid.Tuple) or isinstance(target, astroid.AssignName) or \
                           isinstance(target, astroid.AssignAttr)
                    if isinstance(target, astroid.Tuple):
                        # Tuple assignment, so `<target_x>` is something like `<element_1, element_2, ...>`
                        target_name_list = []
                        for element in target.elts:
                            assert isinstance(element, astroid.AssignName) or \
                                   isinstance(element, astroid.AssignAttr)
                            if isinstance(element, astroid.AssignName) and element.name not in global_names:
                                # `name` is referencing a class attribute
                                target_name_list.append(element.name)
                            else:  # isinstance(element, astroid.AssignAttr) or element.name in global_names
                                # `name` is not referencing a class attribute
                                target_name_list.append(None)
                        # Yield the tuple only if there is at least one valid assignment to a class attribute
                        for name in target_name_list:
                            if name is not None:
                                yield target_name_list, None, cls_body_node.value, cls_body_node,
                                break
                    elif isinstance(target, astroid.AssignName):
                        # Single named target, so `<target_x>` is something like `<element_1>`
                        if target.name not in global_names:
                            # `name` is referencing a class attribute, yield the tuple
                            yield target.name, None, cls_body_node.value, cls_body_node,
                    else:  # isinstance(target, astroid.AssignAttr)
                        # Single named attribute target, so `<target_x>` is something like `<object.attr>`, and cannot
                        #  be a class attribute
                        pass
            elif isinstance(cls_body_node, astroid.AnnAssign):
                # Assignment with annotation, such as: `<target>: <annotation> = <expression>`
                # Chained assignment (`<t_1> = <t_2> = ... = <expr>`) and tuple assignment (`<n_1, n_2, ...> = <expr>`)
                #  cannot occur in annotation assignments
                target = cls_body_node.target
                assert isinstance(target, astroid.AssignName) or isinstance(target, astroid.AssignAttr)
                if isinstance(target, astroid.AssignName):
                    if target.name not in global_names:
                        # `name` is referencing a class attribute, yield the tuple
                        yield target.name, cls_body_node.annotation, cls_body_node.value, cls_body_node,
                else:  # isinstance(target, astroid.AssignAttr)
                    # Single named attribute target, so <target> is something like <object.attr>, and cannot be a class
                    #  attribute
                    pass

    def get_tavn_list_constructor(cls_node: astroid.ClassDef, ctor_node: astroid.FunctionDef) -> Generator[Tuple, None, None]:
        """2) Gets the assignments tuples '(target, annotation, value, node,)' from a constructor body."""
        assert isinstance(cls_node, astroid.ClassDef) and \
               isinstance(ctor_node, astroid.FunctionDef) and ctor_node.name == "__init__"

        if not ctor_node.body or is_static_method(ctor_node):
            # If there is no body, there is no `__init__` declaration nor inheritance from other ancestors constructors,
            #  so no attributes can be declared here.
            # Furthermore, if for some bizarre reason the `__init__` constructor has been tagged as 'static', there is
            #  no self-reference to the object, thus no attributes can be declared here either.
            pass
        else:
            # Find the name of the parameter used for self-reference
            self_ref = get_self_ref(ctor_node)
            assert self_ref

            # Check the body for self-assignments and calls to ancestor constructors
            for ctor_body_node in ctor_node.body:

                # - Self-assignments check
                if isinstance(ctor_body_node, astroid.Assign):
                    # Assignment with no annotation, such as: `<target_1> = <target_2> = ... = <expression>`
                    for target in ctor_body_node.targets:
                        assert isinstance(target, astroid.Tuple) or isinstance(target, astroid.AssignName) or \
                               isinstance(target, astroid.AssignAttr)
                        if isinstance(target, astroid.Tuple):
                            # Tuple assignment, so `<target_x>` is something like `<element_1, element_2, ...>`
                            target_name_list = []
                            for element in target.elts:
                                assert isinstance(element, astroid.AssignName) or \
                                       isinstance(element, astroid.AssignAttr)
                                if isinstance(element, astroid.AssignAttr):
                                    assert isinstance(element.expr, astroid.Name)
                                if isinstance(element, astroid.AssignAttr) and element.expr.name == self_ref:
                                    # `name` is referencing a class attribute through self-reference
                                    target_name_list.append(element.attrname)
                                else:  # isinstance(element, astroid.AssignName) or element.expr.name != self_ref
                                    # `name` is not referencing a class attribute
                                    target_name_list.append(None)
                            # Yield the tuple only if there is at least one valid assignment to a class attribute
                            for name in target_name_list:
                                if name is not None:
                                    yield target_name_list, None, ctor_body_node.value, ctor_body_node,
                                    break
                        elif isinstance(target, astroid.AssignAttr):
                            # Single named target, so `<target_x>` is something like `<object.attr>`, and if `object`
                            #  is a self-reference then it is a class attribute assignment
                            assert isinstance(target.expr, astroid.Name)
                            if target.expr.name == self_ref:
                                yield target.attrname, None, ctor_body_node.value, ctor_body_node,
                        else:  # isinstance(target, astroid.AssignName)
                            # Single named attribute target, so `<target_x>` is something like `<element_1>`, and cannot
                            #  be a class attribute without self-reference
                            pass
                elif isinstance(ctor_body_node, astroid.AnnAssign):
                    # Assignment with annotation, such as: `<target>: <annotation> = <expression>`
                    # Chained assignment (`<t_1> = <t_2> = ... = <expr>`) and tuple assignment
                    #  (`<n_1, n_2, ...> = <expr>`) cannot occur in annotation assignments
                    target = ctor_body_node.target
                    assert isinstance(target, astroid.AssignName) or isinstance(target, astroid.AssignAttr)
                    if isinstance(target, astroid.AssignAttr):
                        assert isinstance(target.expr, astroid.Name)
                        if target.expr.name == self_ref:
                            # `name` is referencing a class attribute, yield the tuple
                            yield target.attrname, ctor_body_node.annotation, ctor_body_node.value, ctor_body_node,
                    else:  # isinstance(target, astroid.AssignName)
                        # Single named attribute target, so `<target_x>` is something like `<element_1>`, and cannot
                        #  be a class attribute without self-reference
                        pass

                # - Constructor calls check
                elif isinstance(ctor_body_node, astroid.Expr) and isinstance(ctor_body_node.value, astroid.Call):
                    # Constructor calls (`__init__` calls) can be done in two ways:
                    #  1) Using `super()` to get a object reference to the first matching constructor in the MRO, as in
                    #      `super().__init__(<params>)`;
                    #  2) Using the explicit name of the class to choose a constructor from a specific ancestor, and
                    #      passing the self-reference object as in `AncestorClass.__init__(<self-ref>, <params>)`

                    call_func, call_params = ctor_body_node.value.func, ctor_body_node.value.args
                    if isinstance(call_func, astroid.Attribute) and call_func.attrname == "__init__":
                        # Check case 1)
                        if isinstance(call_func.expr, astroid.Call):
                            init_caller = getattr(call_func.expr.func, "name", None)
                            if init_caller and init_caller == "super":
                                init_found = False
                                for ancestor_node in cls_node.mro()[1:]:  # First in MRO is the parent class itself
                                    for method_node in ancestor_node.methods():
                                        if method_node.name == "__init__":
                                            yield from get_tavn_list_constructor(ancestor_node, method_node)
                                            init_found = True  # No overload in Python, so just one constructor
                                            break
                                    if init_found:
                                        break
                        # Check case 2)
                        if isinstance(call_func.expr, astroid.Name):
                            ancestor_name = call_func.expr.name
                            ancestor_node = None
                            for ancestor in cls_node.ancestors(recurs=True):
                                if ancestor.name == ancestor_name:
                                    ancestor_node = ancestor
                                    break
                            if ancestor_node:
                                for method_node in ancestor_node.methods():
                                    if method_node.name == "__init__":
                                        yield from get_tavn_list_constructor(ancestor_node, method_node)
                                        break  # No overload in Python, so just one constructor

    assert isinstance(class_node, astroid.ClassDef)
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


def is_static_method(func_node: astroid.FunctionDef) -> bool:
    """Tells if a method is a static method by looking at its decorators. A function is always considered static.

    Args:
        func_node (astroid.FunctionDef): a node representing a function/method definition and body.

    Returns:
        bool: `True` if the node represents a static method or a function, `False` otherwise.

    """
    assert isinstance(func_node, astroid.FunctionDef)
    if func_node.is_method():
        decorators_nodes = func_node.decorators.nodes if func_node.decorators else []
        decorators_names = {node.name for node in decorators_nodes}
        is_static = "staticmethod" in decorators_names
    else:
        is_static = True
    return is_static


def get_self_ref(fun_node: astroid.FunctionDef) -> str:
    """Gets the name used to self-reference the object in a method.

    Notes:
     Conventionally 'self' is used, but it is not mandatory, so it may be different.

    Args:
        fun_node (astroid.FunctionDef): a node representing a function/method definition and body.

    Returns:
        str: the name of the variable representing the object itself within the method, or an empty string if the method
         is static or it is instead a function.

    """
    assert isinstance(fun_node, astroid.FunctionDef)

    self_ref = ""
    if not is_static_method(fun_node):
        # In order of definition we have `posonlyargs`, `args`, `vararg`, `kwonlyargs` and `kwarg`; the name used for
        #  self-reference in methods always occupies the first position in the arguments definition.
        if fun_node.args.posonlyargs:
            self_ref = fun_node.args.posonlyargs[0].name
        else:
            self_ref = fun_node.args.args[0].name
    return self_ref
