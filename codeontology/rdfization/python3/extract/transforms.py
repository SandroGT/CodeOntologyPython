"""Transform functions on AST nodes to increase their expressiveness."""

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
    def _transform_FunctionDef(node: astroid.FunctionDef):
        """Transforms to perform on a 'FunctionDef' node.

        Args:
            node (astroid.FunctionDef): input node.

        """
        def add_method_overrides(node: astroid.FunctionDef):
            """Adds a new `overrides` attribute to a node of type `FunctionDef`, linking it to the node of the method it
             is overriding (if any) or to `None` (if nothing is being overridden or it is not a method).

            Args:
                node (astroid.FunctionDef): a node representing a function/method/constructor definition and body.

            """
            assert isinstance(node, astroid.FunctionDef)

            if not isinstance(node, astroid.FunctionDef):
                raise Exception("Wrong transformation call.")
            # Set 'overrides' default value
            node.overrides = None
            # Search for the possible overridden method
            if node.is_method():
                assert isinstance(node.parent, astroid.ClassDef)
                ancestors_mro = node.parent.mro()[1:]  # First in MRO is the parent class itself
                for ancestor_node in ancestors_mro:
                    for ancestor_method_node in ancestor_node.methods():
                        # In Python methods are identified just by their names, there is no "overloading"
                        if ancestor_method_node.name == node.name:
                            # Set and terminate search
                            node.overrides = ancestor_method_node
                            return

        add_method_overrides(node)

    @staticmethod
    def _transform_ClassDef(node: astroid.ClassDef):
        """Transforms to perform on a 'ClassDef' node.

        Args:
            node (astroid.ClassDef): input node.

        """
        def add_class_fields(node: astroid.ClassDef):
            """Adds a new field `TODO` to represent all the recognized fields/attributes/class variables of the class.

            The fields of a class in Python can only be determined with certainty at runtime, but we can try to predict
             at least the most obvious field by looking at the assignments (but not deletions) to the class object
             itself in constructor methods.

            Args:
                node (astroid.ClassDef): a node representing a class definition and body.

            """
            assert isinstance(node, astroid.ClassDef)
            from transforms_utils import get_tavn_list

            # TODO CONTINUE FROM HERE AND USE get_tavn_list PROPERLY

            fields_dict = dict()

            # TODO add get type from value
            for annotation, target, value, def_node in get_tavn_list(node):  # get annotation, names, value list
                # praticamente scorro tutti gli assegnamenti associabili ad un campo in ordine, e ora devo costruire il
                #  dizionario dei campi a partire dalla lista già correttamente ordinata di assegnamenti
                # print(annotation, target, value, def_node)
                if isinstance(target, list):  # se ho più target era un assegnamento multiplo
                    # Gli assegnamenti multipli (di tuple) sono possibili solo con Assign, non AnnAssign,
                    #  quindi l'annotazione è assente
                    assert annotation is None
                    # Il tipo lo si può ottenere solo da inferenza sul valore, che per ora ignoriamo!
                    # Ma se c'è l'annotazione sfruttiamo quella, quindi inferisci solo se non c'è una annotazione successiva
                    inferred_annotation = None
                    for name in target:
                        prev_annotation, _, _ = fields_dict.get(name, (None, None, None,))
                        fields_dict[name] = (prev_annotation, value, def_node)
                else:  # altrimenti assegnamento singolo
                    assert isinstance(target, str)
                    try:
                        built_type = resolve_annotation(annotation)
                    except Exception:
                        built_type = None
                    fields_dict[target] = (built_type, value, def_node)

            node.fields_dict = fields_dict

        add_class_fields(node)

    @staticmethod
    def _transform_Arguments(node: astroid.Arguments):
        """Transforms to perform on a 'Arguments' node.

        Args:
            node (astroid.Arguments): input node.

        """
        def add_args_type(node: astroid.Arguments):
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
                node (astroid.Arguments): a node representing the arguments of a function/method/constructor.

            """
            assert isinstance(node, astroid.Arguments)
            from transforms_utils import resolve_annotation

            if not isinstance(node, astroid.Arguments):
                raise Exception("Wrong transformation call.")

            for i, ann_attr_name in enumerate(["annotations", "posonlyargs_annotations", "kwonlyargs_annotations",
                                               "varargannotation", "kwargannotation"]):
                ann_attr = getattr(node, ann_attr_name)
                if i > 2:  # Only for "varargannotation" and "kwargannotation", that are not lists
                    ann_attr = [ann_attr]
                type_ann_attr = []

                # Try to link any annotation to a type, defined by a node from an AST. Just link to `None` at fail
                for ann in ann_attr:
                    try:
                        structured_ann = resolve_annotation(ann)
                    except Exception:
                        structured_ann = None
                    type_ann_attr.append(structured_ann)

                # Add the resolved (or not) annotations to the `Arguments` node
                if i > 2:  # Only for "varargannotation" and "kwargannotation", that are not lists
                    assert len(type_ann_attr) == 1
                    type_ann_attr = type_ann_attr[0]
                setattr(node, f"type_{ann_attr_name}", type_ann_attr)

        add_args_type(node)

    @staticmethod
    def _transform_Expr(node: astroid.Expr):
        """Transforms to perform on a 'Expr' node.

        Args:
            node (astroid.Expr): input node.

        """
        # TODO FINISH THIS
        def add_expression_type(node: astroid.Expr):
            assert isinstance(node, astroid.Expr)
            class_type = None
            try:
                infers = node.value.inferred()
            except Exception:
                infers = []
            assert isinstance(infers, list)
            if len(infers) == 1:  # Solo risposte certe
                inferred_value = infers[0]
                if inferred_value is not Uninferable:
                    assert getattr(inferred_value, "pytype", None) is not None
                    complete_inferred_type = inferred_value.pytype()
                    assert "." in complete_inferred_type
                    assert complete_inferred_type.startswith(f"builtins.") or \
                           complete_inferred_type.startswith(f"{node.root().name}.")  # node.root().name potrebbe essere vuoto
                    inferred_type = ".".join(complete_inferred_type.split(".")[1:])
                    print(f"[DEBUG] {inferred_type} ({type(inferred_type)})")
                    scope = node.scope()
                    assert scope
                    try:
                        class_type = lookup_type_by_name(scope, inferred_type)
                    except Exception:
                        pass
            node.class_type = class_type

        add_expression_type(node)
