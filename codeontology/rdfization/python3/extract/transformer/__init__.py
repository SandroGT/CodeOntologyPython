"""Class and methods to visit the AST nodes and apply transform functions to increase their expressiveness."""

from typing import Set, Union
from threading import Thread

import astroid
from tqdm import tqdm

from codeontology import LOGGER
from codeontology.rdfization.python3.explore import Package
from codeontology.rdfization.python3.extract.parser import CommentParser
from codeontology.rdfization.python3.extract.transformer.utils import is_static_method
from codeontology.rdfization.python3.extract.utils import get_parent_node
from codeontology.utils import pass_on_exception


class Transformer:
    """A collection of methods to integrate the information carried by the AST nodes of 'astroid'."""

    def __init__(self, packages: Set[Package]):
        """Launches the application of the proper transformations on the AST nodes of the respective packages.

        Args:
            packages (Set[Package]): the set of packages on which to apply the transformations.

        """
        for package in tqdm(list(packages)):
            t = Thread(target=self.visit_to_transform, args=[package.ast])
            t.start()
            t.join()

    @staticmethod
    def visit_to_transform(node: astroid.NodeNG) -> None:
        def get_transform_fun_name(_node: astroid.NodeNG) -> str:
            _type_name = type(_node).__name__
            return "_transform_" + \
                _type_name[0].lower() + "".join([ch if ch.islower() else "_" + ch.lower() for ch in _type_name[1:]])

        transform_function_name = get_transform_fun_name(node)
        transform_function = getattr(Transformer, transform_function_name, None)
        if transform_function:
            transform_function(node)
        for child in node.get_children():
            if child:
                Transformer.visit_to_transform(child)

    @staticmethod
    def _transform_module(module_node: astroid.Module):
        LOGGER.debug(f"Applying `Module` transform to '{module_node.name}' ('{module_node.file}').")
        Transformer._add_description(module_node)

    @staticmethod
    def _transform_function_def(function_node: Union[astroid.FunctionDef, astroid.AsyncFunctionDef]):
        def add_method_overrides(fun_node: Union[astroid.FunctionDef, astroid.AsyncFunctionDef]):
            """Adds a new `overrides` attribute to a node of type `FunctionDef`, linking it to the node of the method it
             is overriding (if any) or to `None` (if nothing is being overridden or it is not a method).

            Args:
                fun_node (astroid.FunctionDef): a node representing a function/method/constructor definition and body.

            """
            assert type(fun_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef]

            # Set 'overrides' default value
            fun_node.overrides = None
            # Search for the possible overridden method
            if fun_node.is_method():
                # Methods definition may be enclosed in 'if statements' (maybe even try-except?) and not directly be in
                #  the class body, so we have to search for the class node further than the direct parent node
                node = fun_node
                while not type(node) is astroid.Module:
                    if type(node) is astroid.ClassDef:
                        break
                    node = node.parent
                assert type(node) is astroid.ClassDef
                class_node = node
                ancestors_mro = class_node.mro()[1:]  # First in MRO is the parent class itself
                for ancestor_node in ancestors_mro:
                    for ancestor_method_node in ancestor_node.methods():
                        # In Python methods are identified just by their names, there is no "overloading"
                        if ancestor_method_node.name == fun_node.name:
                            # Set and terminate search
                            fun_node.overrides = ancestor_method_node
                            return

        def add_return(function_node: Union[astroid.FunctionDef, astroid.AsyncFunctionDef]):
            """TODO Adds a new `returns_type` and `returns_description` attribute"""
            from codeontology.rdfization.python3.extract.transformer.tracking import resolve_annotation

            return_type, return_description = CommentParser.get_return_info(function_node)
            if function_node.returns is not None:
                return_type = function_node.returns
            function_node.returns_type = resolve_annotation(return_type, context_node=function_node)
            function_node.returns_description = \
                "Returns: " + return_description.strip() if return_description is not None else return_description

        LOGGER.debug(f"Applying `FunctionDef` transform to '{function_node.name}'"
                     f" (from '{function_node.root().file}').")
        add_method_overrides(function_node)
        add_return(function_node)
        Transformer._add_description(function_node)

    @staticmethod
    def _transform_async_function_def(function_node: astroid.AsyncFunctionDef):
        # They practically are the same, so we just redirect the call
        Transformer._transform_function_def(function_node)

    @staticmethod
    def _transform_class_def(class_node: astroid.ClassDef):
        def add_class_fields(cls_node: astroid.ClassDef):
            """Adds a new attribute `fields` to represent all the recognized fields/attributes/class variables of the
             class. The new attribute will contain a dictionary `{<field>: (<structured annotation>,
             <declaring node>,)}`. The <structured annotation> respects the 'structured annotation' criteria described
             in `codeontology.rdfization.python3.exract.transformer.tracking.resolve_annotation()`.

            The fields of a class in Python can only be determined with certainty at runtime, but we can try to predict
             at least the most obvious fields by looking at the assignments (but not deletions) to the class object
             itself in class body and constructor methods.

            Args:
                cls_node (astroid.ClassDef): a node representing a class definition and body.

            """
            assert type(cls_node) is astroid.ClassDef
            from codeontology.rdfization.python3.extract.transformer.tracking import \
                resolve_annotation, resolve_value, track_fields

            # Get the list of assignments to potential fields in the class with `get_tavn_list`. It organizes these
            #  assignments on a dictionary by `field` (whose name is found in the assignment `target` value). Since the
            #  list is ordered from oldest to newest assignment, when a field is encountered more than once, it
            #  overwrites the previously assigned annotation, description and value (if provided), while node always
            #  stays on the oldest node available (because we are interested in the oldest declaration).
            favn_dict = dict()  # {field: (annotation, description, value, node,)}
            for target, description, annotation, value, node in track_fields(cls_node):
                assert type(target) is str
                assert type(node) in [astroid.AssignName, astroid.AssignAttr]
                field = target
                prev_annotation, prev_description, prev_value, prev_node = \
                    favn_dict.get(field, (None, None, None, None,))
                ref_annotation = annotation if annotation is not None else prev_annotation      # Newest takes priority
                ref_description = description if description is not None else prev_description  # Newest takes priority
                ref_value = value if value is not None else prev_value                          # Newest takes priority
                ref_node = prev_node if prev_node is not None else node                         # Oldest takes priority
                favn_dict[field] = (ref_annotation, ref_description, ref_value, ref_node,)

            # Use the annotation and value information from the dictionary to infer the field type
            ftn_dict = {}  # {field: (type, description, node,)}
            for field, (annotation, description, value, node) in favn_dict.items():
                structured_annotation = None
                if annotation:
                    with pass_on_exception((RecursionError,)):
                        # TODO Investigate `RecursionError`.
                        structured_annotation = resolve_annotation(annotation, context_node=node)
                if value and not structured_annotation:
                    structured_annotation = resolve_value(value)
                ftn_dict[field] = (structured_annotation, description, node,)
            cls_node.fields = ftn_dict

        LOGGER.debug(f"Applying `ClassDef` transform to '{class_node.name}' (from '{class_node.root().file}').")
        add_class_fields(class_node)
        Transformer._add_description(class_node)

    @staticmethod
    def _transform_arguments(arguments_node: astroid.Arguments):
        def add_args_info(args_node: astroid.Arguments):
            """TODO 
            Adds a `params` that is a list attribute with tuples of:
                name: str,
                position (None if not positional): int | None,
                type: Union[astroid.ClassDef, List, Tuple, None],
                description: str |  None,
                is_var_arg: bool,
                is_pos_only: bool,
                is_key_only: bool,

            Adds `is_var_args: bool` to the parent function FunctionDef
            """
            assert type(args_node) is astroid.Arguments
            from codeontology.rdfization.python3.extract.transformer.tracking import resolve_annotation, resolve_value

            if args_node.parent.name == "relation_expansion":
                a = 0
                pass

            executable_node = args_node.parent
            assert type(executable_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef, astroid.Lambda]

            # Parameters field in the `args_node` ordered by position in the signature
            args_fields = [
                # arg_field_name, ann_field_name,            is_positional, is_vararg
                ("posonlyargs",   "posonlyargs_annotations", True,          False,),
                ("args",          "annotations",             True,          False,),
                ("vararg",        "varargannotation",        False,         True,),
                ("kwonlyargs",    "kwonlyargs_annotations",  False,         False,),
                ("kwarg",         "kwargannotation",         False,         True,),
            ]

            # Read all the parameters and accumulate them
            parameters = []
            is_var_args = False
            if type(executable_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef] and \
                    executable_node.is_method() and not is_static_method(executable_node):
                is_self_reference = True
            else:
                is_self_reference = False
            for arg_field_name, ann_field_name, is_positional, is_vararg in args_fields:
                arg_field = getattr(args_node, arg_field_name)
                ann_field = getattr(args_node, ann_field_name)
                if type(arg_field) is not list:
                    arg_field = [arg_field] if arg_field is not None else []
                    ann_field = [ann_field] if ann_field is not None else []
                if is_vararg and arg_field:
                    is_var_args = True

                for i, (arg, ann) in enumerate(zip(arg_field, ann_field)):
                    if is_vararg:
                        assert type(arg) is str
                        arg_name = arg
                    else:
                        assert type(arg) in [astroid.AssignName, astroid.Name]
                        arg_name = arg.name

                    comment_description, comment_ann = \
                        CommentParser.get_param_info(arg_name, executable_node, type(executable_node))
                    ann = comment_ann if not ann else ann

                    if is_self_reference:
                        type_ = get_parent_node(executable_node, {astroid.ClassDef})
                        is_self_reference = False
                    else:
                        type_ = None
                        if ann:
                            with pass_on_exception((RecursionError,)):
                                # TODO Investigate `RecursionError`.
                                type_ = resolve_annotation(ann, context_node=args_node)
                        if not type_:
                            value = None
                            if arg_field_name == "args":
                                i_first_default = len(args_node.args) - len(args_node.defaults)
                                if i >= i_first_default:
                                    assert i < len(args_node.args)
                                    value = args_node.defaults[i - i_first_default]
                            elif arg_field_name == "kwonlyargs":
                                assert 0 <= i < len(args_node.kw_defaults)
                                value = args_node.kw_defaults[i]
                            if value:
                                type_ = resolve_value(value)

                    parameters.append((
                        arg_name,
                        i if is_positional else None,
                        type_,
                        comment_description,
                        is_vararg,
                        arg_field_name == "posonlyargs",
                        arg_field_name == "kwonlyargs",
                    ))
                    assert type(parameters[-1]) is tuple

            args_node.params = parameters
            executable_node.is_var_args = is_var_args

        LOGGER.debug(f"Applying `Arguments` transform to '{arguments_node.parent.name}'"
                     f" (from '{arguments_node.root().file}')")
        add_args_info(arguments_node)

    @staticmethod
    def _transform_import(import_node: astroid.Import):
        def add_imported_modules(_import_node: astroid.Import):
            """Adds a new `references` attribute to a node of type `Import`, linking the names in the import statement
             to the AST nodes of the respective modules. The new attribute is therefore a list with an entry for every
             imported name, with each entry being either a `astroid.Module` node or `None` (unresolved matches).

            Args:
                _import_node (astroid.Import): a node representing an 'import statement'.

            """
            references = []
            for name, alias in _import_node.names:
                try:
                    module = import_node.do_import_module(name)
                    references.append(module)
                except (astroid.AstroidImportError, ImportError,):
                    references.append(None)
            assert len(references) == len(_import_node.names)
            _import_node.references = references

        LOGGER.debug(f"Applying `Import` transform to statement on line '{import_node.lineno}'"
                     f" (from '{import_node.root().file}')")
        add_imported_modules(import_node)

    @staticmethod
    def _transform_import_from(import_node: astroid.ImportFrom):
        def add_imported_objects(_import_node: astroid.ImportFrom):
            """Adds a new `references` attribute to a node of type `ImportFrom`, linking the names in the import from
             statement to the AST nodes of the respective objects. The new attribute is therefore a list with an entry
             for every imported name (excluding the case of wildcard imports), with each entry being either `None`
             (unresolved matches) or a list of nodes of type:
              - `astroid.Module` for imported modules/packages;
              - `astroid.ClassDef` for imported classes;
              - `astroid.FunctionDef` for imported functions;
              - `astroid.Assign`, `astroid.AssignName`, `astroid.AssignAttr` and `astroid.AnnAssign` for imported global
                 variables/names;
            Unlike the `Import` case, in which there will be no match or a single match, with the import from statement
             there can be multiple matches, caused by possible conditional declarations (e.g., an if-else in which the
             same name is defined in different ways, usually OS-dependent).

            Args:
                _import_node (astroid.ImportFrom): a node representing an 'import from statement'.

            """
            from codeontology.rdfization.python3.extract.transformer.tracking import \
                track_name_from_scope, TrackingFailException

            references = []
            if _import_node.names[0] == "*":
                # We have a wildcard import, so we are importing all the content from a module/package
                assert len(_import_node.names) == 1
                with pass_on_exception((astroid.AstroidError,)):
                    module: astroid.Module = _import_node.do_import_module(f"{_import_node.modname}")
                    for imported_name in module.wildcard_import_names():
                        tracked = track_name_from_scope(imported_name, _import_node, module)
                        references.append(tracked if tracked else None)
                    assert len(references) == len(module.wildcard_import_names())
            else:
                # We have not a wildcard import: we have to discover the nature of what we are importing: is it a
                #  module/package or another object?
                for name, alias in _import_node.names:
                    try:
                        module: astroid.Module = _import_node.do_import_module(f"{_import_node.modname}.{name}")
                        # It is a module/package
                        references.append(module)
                    except (astroid.AstroidImportError, ImportError,):
                        # It is not a module/package
                        try:
                            module: astroid.Module = _import_node.do_import_module(f"{_import_node.modname}")
                            tracked = track_name_from_scope(name, _import_node, module)
                            references.append(tracked if tracked else None)
                        except (astroid.AstroidError, TrackingFailException):
                            references.append(None)
                assert len(references) == len(_import_node.names)
            assert type(references) is list
            _import_node.references = references

        LOGGER.debug(f"Applying `ImportFrom` transform to statement on line '{import_node.lineno}'"
                     f" (from '{import_node.root().file}')")
        add_imported_objects(import_node)

    @staticmethod
    def _transform_ann_assign(ann_assign_node: astroid.AnnAssign):
        def add_structured_annotation(_ann_assign_node: astroid.AnnAssign):
            """TOCOMMENT"""
            from codeontology.rdfization.python3.extract.transformer.tracking import resolve_annotation
            ann_assign_node.structured_annotation = resolve_annotation(ann_assign_node.annotation)

        LOGGER.debug(f"Applying `Name` transform to statement on line '{ann_assign_node.lineno}'"
                     f" (from '{ann_assign_node.root().file}')")
        add_structured_annotation(ann_assign_node)


    @staticmethod
    def _transform_name(name_node: astroid.Name):
        def add_reference(_name_node: astroid.Name):
            """TOCOMMENT"""
            from codeontology.rdfization.python3.extract.transformer.tracking import \
                track_name_from_local, TrackingFailException
            with pass_on_exception((TrackingFailException, astroid.AstroidError, RecursionError,)):
                _name_node.reference = track_name_from_local(_name_node)

        LOGGER.debug(f"Applying `Name` transform to statement on line '{name_node.lineno}'"
                     f" (from '{name_node.root().file}')")
        add_reference(name_node)

    @staticmethod
    def _transform_assign_name(assign_name_node: astroid.AssignName):
        def add_reference(_assign_name_node: astroid.AssignName):
            """TOCOMMENT"""
            from codeontology.rdfization.python3.extract.transformer.tracking import \
                track_name_from_local, TrackingFailException
            with pass_on_exception((TrackingFailException, astroid.AstroidError, RecursionError,)):
                ref = track_name_from_local(_assign_name_node)
                if type(ref) in [astroid.AssignName, astroid.AssignAttr]:
                    ref_parent = get_parent_node(ref, {astroid.Assign, astroid.AnnAssign, astroid.AugAssign})
                    if type(ref_parent) is astroid.AugAssign:
                        ref = None
                if ref is not None:
                    assign_name_node.reference = ref

        LOGGER.debug(f"Applying `AssignName` transform to statement on line '{assign_name_node.lineno}'"
                     f" (from '{assign_name_node.root().file}')")
        add_reference(assign_name_node)

    @staticmethod
    def _transform_attribute(attribute_node: astroid.Attribute):
        def add_reference(_attribute_node: astroid.Attribute):
            """TOCOMMENT"""
            from codeontology.rdfization.python3.extract.transformer.tracking import \
                track_attr_from_local, TrackingFailException
            with pass_on_exception((TrackingFailException, astroid.AstroidError, RecursionError,)):
                _attribute_node.reference = track_attr_from_local(_attribute_node)

        LOGGER.debug(f"Applying `Attribute` transform to statement on line '{attribute_node.lineno}'"
                     f" (from '{attribute_node.root().file}')")
        add_reference(attribute_node)

    @staticmethod
    def _transform_assign_attr(assign_attr_node: astroid.AssignAttr):
        def add_reference(_assign_attr_node: astroid.AssignAttr):
            """TOCOMMENT"""
            from codeontology.rdfization.python3.extract.transformer.tracking import \
                track_attr_from_local, TrackingFailException
            with pass_on_exception((TrackingFailException, astroid.AstroidError, RecursionError,)):
                ref = track_attr_from_local(_assign_attr_node)
                if type(ref) in [astroid.AssignName, astroid.AssignAttr]:
                    ref_parent = get_parent_node(ref, {astroid.Assign, astroid.AnnAssign, astroid.AugAssign})
                    if type(ref_parent) is astroid.AugAssign:
                        ref = None
                if ref is not None:
                    _assign_attr_node.reference = ref

        LOGGER.debug(f"Applying `AssignAttr` transform to statement on line '{assign_attr_node.lineno}'"
                     f" (from '{assign_attr_node.root().file}')")
        add_reference(assign_attr_node)

    @staticmethod
    def _add_description(node: astroid.NodeNG):
        """TOCOMMENT"""
        if hasattr(node, "doc_node"):
            node.description = CommentParser.get_description(node)
