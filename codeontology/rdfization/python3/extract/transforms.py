"""Class and methods to visit the AST nodes and apply transform functions to increase their expressiveness."""

import astroid

from codeontology import logger
from codeontology.utils import pass_on_exception


class Transformer:
    """A collection of methods to integrate the information carried by the AST nodes of 'astroid'."""

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
    def _transform_function_def(function_node: astroid.FunctionDef):
        def add_method_overrides(fun_node: astroid.FunctionDef):
            """Adds a new `overrides` attribute to a node of type `FunctionDef`, linking it to the node of the method it
             is overriding (if any) or to `None` (if nothing is being overridden or it is not a method).

            Args:
                fun_node (astroid.FunctionDef): a node representing a function/method/constructor definition and body.

            """
            assert isinstance(fun_node, astroid.FunctionDef)

            # Set 'overrides' default value
            fun_node.overrides = None
            # Search for the possible overridden method
            if fun_node.is_method():
                # Methods definition may be enclosed in 'if statements' (maybe even try-except?) and not directly be in
                #  the class body, so we have to search for the class node further than the direct parent node
                node = fun_node
                while not isinstance(node, astroid.Module):
                    if isinstance(node, astroid.ClassDef):
                        break
                    node = node.parent
                assert isinstance(node, astroid.ClassDef)
                class_node = node
                ancestors_mro = class_node.mro()[1:]  # First in MRO is the parent class itself
                for ancestor_node in ancestors_mro:
                    for ancestor_method_node in ancestor_node.methods():
                        # In Python methods are identified just by their names, there is no "overloading"
                        if ancestor_method_node.name == fun_node.name:
                            # Set and terminate search
                            fun_node.overrides = ancestor_method_node
                            return

        logger.debug(f"Applying `FunctionDef` transform to '{function_node.name}' (from '{function_node.root().file}')")
        add_method_overrides(function_node)

    @staticmethod
    def _transform_class_def(class_node: astroid.ClassDef):
        def add_class_fields(cls_node: astroid.ClassDef):
            """Adds a new attribute `fields` to represent all the recognized fields/attributes/class variables of the
             class. The new attribute will contain a dictionary `{<field>: (<field type>, <declaring node>,)}`.

            The fields of a class in Python can only be determined with certainty at runtime, but we can try to predict
             at least the most obvious fields by looking at the assignments (but not deletions) to the class object
             itself in class body and constructor methods.

            Args:
                cls_node (astroid.ClassDef): a node representing a class definition and body.

            """
            assert isinstance(cls_node, astroid.ClassDef)
            from codeontology.rdfization.python3.extract.transforms_utils import \
                get_tavn_list, resolve_annotation, resolve_value

            # Get the list of assignments to potential fields in the class with `get_tavn_list`. It organizes these
            #  assignments on a dictionary by `field` (whose name is found in the assignment `target` value). Since the
            #  list is ordered from oldest to newest assignment, when a field is encountered more than once, it
            #  overwrites the previously assigned annotation, value, and node (if provided).
            favn_dict = dict()  # {field: (annotation, value, node,)}
            for target, annotation, value, node in get_tavn_list(cls_node):
                if isinstance(target, list):  # Multiple targets from tuple assignments
                    assert annotation is None  # Tuple assignments cannot be annotated, so no astroid.AnnAssign
                    for field in target:
                        if field:
                            prev_annotation, _, _ = favn_dict.get(field, (None, None, None))
                            # !!! We drop and don't use the current `value` since it's a tuple for the entire target:
                            #  we would have to extract the corresponding bit that is assigned exactly to this field,
                            #  and we don't know what that is statically
                            new_annotation = prev_annotation
                            new_value = None
                            new_node = node
                            favn_dict[field] = (new_annotation, new_value, new_node,)
                else:
                    assert isinstance(target, str)
                    field = target
                    prev_annotation, prev_value, _ = favn_dict.get(field, (None, None, None))
                    new_annotation = annotation if annotation else prev_annotation
                    new_value = value if value else prev_value
                    new_node = node
                    favn_dict[field] = (new_annotation, new_value, new_node,)

            # Use the annotation and value information from the dictionary to infer the field type
            ftn_dict = {}  # {field: (type, node,)}
            for field, (annotation, value, node) in favn_dict.items():
                type_ = None
                if annotation:
                    with pass_on_exception((AssertionError,)):
                        # TODO remove `AssertionError`! Assert trigger should help improve the code!
                        type_ = resolve_annotation(annotation)
                # TODO find a way to restore this!
                #  Had to cut this out, because the `astroid`'s `infer()` function used there brings to stack overflow
                # if value and not type_:
                #     type_ = resolve_value(value)
                ftn_dict[field] = (type_, node,)
            cls_node.fields = ftn_dict

        logger.debug(f"Applying `ClassDef` transform to '{class_node.name}' (from '{class_node.root().file}')")
        add_class_fields(class_node)

    @staticmethod
    def _transform_arguments(arguments_node: astroid.Arguments):
        def add_args_type(args_node: astroid.Arguments):
            """Adds a new set of attributes to a node of type `Arguments`, linking its annotations to the AST nodes
             defining the types to which the annotations might refer.

            These are the five added attributes:
             - `type_annotations`, to match the annotations in `annotations` for normal arguments from `args`;
             - `type_posonlyargs_annotations`, to match the annotations in `posonlyargs_annotations` for positional only
                arguments from `posonlyargs`;
             - `type_kwonlyargs_annotations`, to match the annotations in `kwonlyargs_annotations` for keyword only
                arguments from `kwonlyargs`;
             - `type_varargannotation` to match the single annotation in `varargannotation` for the various positional
                arguments from `vararg`;
             - `type_kwargannotation` to match the single annotation in `kwargannotation` for the various keyword
                arguments from `kwarg`.

            So, `type_annotations`, `type_posonlyargs_annotations` and `type_kwonlyargs_annotations` are lists, while
             `type_varargannotation` and `type_kwargannotation` are single valued, matching the cardinality of the
             annotation attributes they are referencing.

            If an annotation is matched with no type, `None` is used in place of the nodes representing the type. If a
             match occurs, then the type is represented by one or more nodes (for 'parameterized' types) according to
             the specifics introduced with the function `resolve_annotation`.

            Args:
                args_node (astroid.Arguments): a node representing the arguments of a function/method/constructor.

            """
            assert isinstance(args_node, astroid.Arguments)
            from codeontology.rdfization.python3.extract.transforms_utils import resolve_annotation

            for i, ann_attr_name in enumerate(["annotations", "posonlyargs_annotations", "kwonlyargs_annotations",
                                               "varargannotation", "kwargannotation"]):
                ann_attr = getattr(args_node, ann_attr_name)
                if i > 2:  # Only for "varargannotation" and "kwargannotation", that are not lists
                    ann_attr = [ann_attr]
                type_ann_attr = []

                # Try to link any annotation to a type, defined by a node from an AST. Just link to `None` at fail
                for ann in ann_attr:
                    try:
                        structured_ann = resolve_annotation(ann)
                    except (RecursionError, AssertionError):
                        # TODO remove `AssertionError`! Assert trigger should help improve the code!
                        #  Investigate `RecursionError`.
                        structured_ann = None
                    type_ann_attr.append(structured_ann)

                # Add the resolved (or not) annotations to the `Arguments` node
                if i > 2:  # Only for "varargannotation" and "kwargannotation", that are not lists
                    assert len(type_ann_attr) == 1
                    type_ann_attr = type_ann_attr[0]
                setattr(args_node, f"type_{ann_attr_name}", type_ann_attr)

        logger.debug(f"Applying `Arguments` transform to '{arguments_node.parent.name}'"
                     f" (from '{arguments_node.root().file}')")
        add_args_type(arguments_node)

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
                except astroid.AstroidImportError:
                    references.append(None)
            assert len(references) == len(_import_node.names)
            _import_node.references = references

        logger.debug(f"Applying `Import` transform to statement on line '{import_node.lineno}'"
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
            from codeontology.rdfization.python3.extract.transforms_utils import track_name

            references = []
            if _import_node.names[0] == "*":
                # We have a wildcard import, so we are importing all the content from a module/package
                assert len(_import_node.names) == 1
                with pass_on_exception((astroid.AstroidError,)):
                    module: astroid.Module = _import_node.do_import_module(f"{_import_node.modname}")
                    for imported_name in module.wildcard_import_names():
                        tracked = track_name(imported_name, module)
                        references.append(tracked if tracked else None)
                    assert len(references) == len(module.wildcard_import_names())
            else:
                # We have not a wildcard import: we have to discover the nature of what we are importing: is it a
                #  module/package or another object?
                for name, alias in _import_node.names:
                    try:
                        module: astroid.Module = _import_node.do_import_module(f"{_import_node.modname}.{name}")
                        # It is a module/package
                        references.append([module])
                    except astroid.AstroidImportError:
                        # It is not a module/package
                        try:
                            module: astroid.Module = _import_node.do_import_module(f"{_import_node.modname}")
                            tracked = track_name(name, module)
                            references.append(tracked if tracked else None)
                        except astroid.AstroidError:
                            references.append(None)
                assert len(references) == len(_import_node.names)
            _import_node.references = references

        logger.debug(f"Applying `ImportFrom` transform to statement on line '{import_node.lineno}'"
                     f" (from '{import_node.root().file}')")
        add_imported_objects(import_node)
