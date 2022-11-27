"""Class and methods to visit the AST nodes and apply transform functions to increase their expressiveness."""

import astroid


class Transformer:
    """A collection of methods to integrate the information carried by the AST nodes of 'astroid'."""

    @staticmethod
    def visit_to_transform(node: astroid.NodeNG) -> None:
        transform_function_name = f"_transform_{type(node).__name__}"
        transform_function = getattr(Transformer, transform_function_name, None)
        if transform_function:
            transform_function(node)
        for child in node.get_children():
            if child:
                Transformer.visit_to_transform(child)

    @staticmethod
    def _transform_FunctionDef(function_node: astroid.FunctionDef):
        """Transforms to perform on a 'FunctionDef' node.

        Args:
            function_node (astroid.FunctionDef): input node.

        """
        def add_method_overrides(fun_node: astroid.FunctionDef):
            """Adds a new `overrides` attribute to a node of type `FunctionDef`, linking it to the node of the method it
             is overriding (if any) or to `None` (if nothing is being overridden or it is not a method).

            Args:
                fun_node (astroid.FunctionDef): a node representing a function/method/constructor definition and body.

            """
            assert isinstance(fun_node, astroid.FunctionDef)

            if not isinstance(fun_node, astroid.FunctionDef):
                raise Exception("Wrong transformation call.")
            # Set 'overrides' default value
            fun_node.overrides = None
            # Search for the possible overridden method
            if fun_node.is_method():
                assert isinstance(fun_node.parent, astroid.ClassDef)
                ancestors_mro = fun_node.parent.mro()[1:]  # First in MRO is the parent class itself
                for ancestor_node in ancestors_mro:
                    for ancestor_method_node in ancestor_node.methods():
                        # In Python methods are identified just by their names, there is no "overloading"
                        if ancestor_method_node.name == fun_node.name:
                            # Set and terminate search
                            fun_node.overrides = ancestor_method_node
                            return

        add_method_overrides(function_node)

    @staticmethod
    def _transform_ClassDef(class_node: astroid.ClassDef):
        """Transforms to perform on a 'ClassDef' node.

        Args:
            class_node (astroid.ClassDef): input node.

        """
        def add_class_fields(cls_node: astroid.ClassDef):
            """Adds a new attribute `fields` to represent all the recognized fields/attributes/class variables of the
             class. The new attribute will contain a dictionary `{<field>: (<field type>, <declaring node>,)}`.

            The fields of a class in Python can only be determined with certainty at runtime, but we can try to predict
             at least the most obvious field by looking at the assignments (but not deletions) to the class object
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
                    type_ = resolve_annotation(annotation)
                if value and not type_:
                    type_ = resolve_value(value)
                ftn_dict[field] = (type_, node,)
            cls_node.fields = ftn_dict

        add_class_fields(class_node)

    @staticmethod
    def _transform_Arguments(arguments_node: astroid.Arguments):
        """Transforms to perform on a 'Arguments' node.

        Args:
            arguments_node (astroid.Arguments): input node.

        """
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

            if not isinstance(args_node, astroid.Arguments):
                raise Exception("Wrong transformation call.")

            for i, ann_attr_name in enumerate(["annotations", "posonlyargs_annotations", "kwonlyargs_annotations",
                                               "varargannotation", "kwargannotation"]):
                ann_attr = getattr(args_node, ann_attr_name)
                if i > 2:  # Only for "varargannotation" and "kwargannotation", that are not lists
                    ann_attr = [ann_attr]
                type_ann_attr = []

                # Try to link any annotation to a type, defined by a node from an AST. Just link to `None` at fail
                for ann in ann_attr:
                    structured_ann = resolve_annotation(ann)
                    type_ann_attr.append(structured_ann)

                # Add the resolved (or not) annotations to the `Arguments` node
                if i > 2:  # Only for "varargannotation" and "kwargannotation", that are not lists
                    assert len(type_ann_attr) == 1
                    type_ann_attr = type_ann_attr[0]
                setattr(args_node, f"type_{ann_attr_name}", type_ann_attr)

        add_args_type(arguments_node)
