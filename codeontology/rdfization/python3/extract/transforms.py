"""Transform functions on AST nodes to increase their expressiveness."""

import astroid


class Transformer:
    """A collection of methods to integrate the information carried by the AST nodes of 'astroid'."""

    @staticmethod
    def transform_add_method_overrides(node: astroid.FunctionDef):
        """Adds a new `overrides` attribute to a node of type `FunctionDef`, linking it to the node of the method it
         is overriding (if any) or to `None` (if nothing is being overridden or it is not a method).

        Args:
            node (FunctionDef): a node representing a function/method/constructor.

        """
        if not isinstance(node, astroid.FunctionDef):
            raise Exception("Wrong transformation call.")
        # Set 'overrides' default value
        node.overrides = None
        # Search for the possible overridden method
        if node.is_method():
            assert isinstance(node.parent, astroid.ClassDef)
            ancestors_mro = node.parent.mro()[1:]  # First in method resolution order (mro) is the parent class itself
            for ancestor_node in ancestors_mro:
                for ancestor_method_node in ancestor_node.methods():
                    # In Python methods are identified just by their names, there is no "overloading"
                    if ancestor_method_node.name == node.name:
                        # Set and terminate search
                        node.overrides = ancestor_method_node
                        return

    @staticmethod
    def transform_add_args_type(node: astroid.Arguments):
        """Adds a new set of attributes to a node of type `Arguments`, linking its annotations to the AST nodes defining
         the types to which the annotations might refer.

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
         match occurs, then the type is represented by one or more nodes (for 'parameterized' types) according to the
         specifics introduced with the function `resolve_annotation`.

        Args:
            node (Arguments): a node representing the arguments of a function/method/constructor.

        """
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
                type_ann = None
                try:
                    structured_text_ann = utils_build_type_annotation(ann)
                    if structured_text_ann:
                        type_ann = convert(structured_text_ann)
                except Exception:
                    pass
                type_ann_attr.append(type_ann)

            # Add the resolved (or not) annotations to the `Arguments` node
            if i > 2:  # Only for "varargannotation" and "kwargannotation", that are not lists
                assert len(type_ann_attr) == 1
                type_ann_attr = type_ann_attr[0]
            setattr(node, f"type_{ann_attr_name}", type_ann_attr)

    @staticmethod
    def transform_add_expression_type(node: Expr):
        assert isinstance(node, Expr)
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

    @staticmethod
    def transforms_add_class_fields(node: nodes.ClassDef):
        assert isinstance(node, nodes.ClassDef)
        fields_dict = dict()

        # TODO add get type from value
        for annotation, target, value, def_node in utils_get_anv_list(node):  #get annotation, names, value list
            # praticamente scorro tutti gli assegnamenti associabili ad un campo in ordine, e ora devo costruire il
            #  dizionario dei campi a partire dalla lista già correttamente ordinata di assegnamenti
            # print(annotation, target, value, def_node)
            if isinstance(target, list):  # se ho più target era un assegnamento multiplo
                # Gli assegnamenti multipli (di tuple) sono possibili solo con Assign, non AnnAssign,
                #  quindi l'annotazione è assente
                assert annotation is None
                # Il tipo lo si può ottenere solo da inferenza, che per ora ignoriamo!
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
            # Definition of the parameterization of a type with multiple values, such as '...[int, float]'
            assert isinstance(ann_node.elts, list)
            structured_ann = [structure_annotation(e) for e in ann_node.elts]

        return structured_ann

    def resolve_class_names(ann_node: ..., structured_ann: ...) -> ...:
        """Resolves the names of the classes in a structured annotation, replacing them with the reference to the
         respective AST Class nodes.
        """
        # Default value, in case it is not possible to resolve the names
        matched_type = None

        # Explore the cases that may constitute the structured annotation
        if structured_ann is None:
            # Absence of the structured annotation info, no matches with any type
            matched_type = None

        # A) Single types (base case)
        elif isinstance(structured_ann, str):
            matched_type = lookup_type_by_name(structured_ann, ann_node)

        # B) Equivalent types (recursive step)
        elif isinstance(structured_ann, list):
            matched_type = [resolve_class_names(ann_node, a) for a in structured_ann]

        # C) Parameterized types (recursive step)
        elif isinstance(structured_ann, tuple):
            matched_type = tuple([resolve_class_names(ann_node, a) for a in structured_ann])

        return matched_type

    try:
        matched_type = resolve_class_names(node, structure_annotation(node))
    except Exception:
        matched_type = None

    return matched_type


def lookup_type_by_name(name: str, node: ...) -> astroid.ClassDef:
    """Looks for the reference to the AST node that defines the type specified by the name, using the scope given by the
     passed node.

    Args:
        name (str): the name of the type/class to search for.
        node: the node that defines the scope from which to start the search.

    Returns:
        astroid.ClassDef: the reference to the type/class corresponding to the name.

    Raises:
        Exception: if the lookup operation fails and finds no match.

    """
    assert isinstance(name, str) and len(name) > 0
    name_parts = name.split(".")
    name_root = name_parts[0]
    name_tail = ".".join(name_parts[1:])
    return track_type_name(name_root, name_tail, node)


def track_type_name(base: str, tail: str, node: ..., c: int = 0) -> astroid.ClassDef:
    """Tracks down the type/class related to the specified name, recursively splitting it into `base` and `tail` until
     there are no more trailing names to follow.

    Args:
        base (str): the first part of the name we want to track down; for example in '<package>.<wrapper_class>.<type>'
         the base is '<package>'. May also concide with the whole name, if no tail exists.
        tail (str): the trailing parts of the name after the `base`; for example in '<package>.<wrapper_class>.<type>'
         the tail is '<wrapper_class>.<type>'. It's `None` at the final step.
        node: the node defining the scope from which to search for the `base`.
        c (int): TODO

    Returns:
        astroid.ClassDef: the reference to the type/class matched to the name.

    Raises:
        Exception: if the tracking down operation fails and finds no match.

    """
    # target = base + "." + tail if tail else base
    # file = getattr(node.root(), "file", None)
    # file_target = file if file else "<UNKNOWN FILE>"
    # print(f"{' '*4} tracking {target} from {file_target} (count:{c:,})")
    # Cerchiamo a partire dal nodo dove è stato definito il nome base per cercare il tipo che deriva
    #  da esso (tail) o che rappresenta direttamente (se tail è assente)
    assert base is not None

    # print(
    #     f"[DEBUG] Cercando il nome {base}{' da cui origina ' + tail + ' ' if tail else ' '}a partire "
    #     f"dal nodo di tipo {type(node).__name__} e nome {node.name}")

    # Cerca da dove arriva il nome del tipo partendo da questo nodo
    _, type_matches = node.lookup(base)
    # print(f"[DEBUG] {type_matches}")

    if type_matches == () or len(type_matches) > 1:
        # Nessun match o match multipli, quindi non si sa esattamente a che tipo si riferisca il nome.
        # Interrompi subito!
        return None

    type_match_node = type_matches[0]
    # print(f"[DEBUG] Match del tipo {type(type_match_node).__type__}")

    # Controlla il tipo del match per continuare il tracking del tipo
    if isinstance(type_match_node, Import) or \
            isinstance(type_match_node, ImportFrom):
        return utils_handle_type_match_Imports(type_match_node, base, tail, c)
    elif isinstance(type_match_node, ClassDef):
        return utils_handle_type_match_ClassDef(type_match_node, base, tail, c)
    elif isinstance(type_match_node, AssignName):
        return utils_handle_type_match_AssignName(type_match_node, base, tail, c)

    # Il match ottenuto è su un tipo di nodo non previsto per il tracking
    return None


def utils_track_type_name(node, base, tail, c=0):
    # target = base + "." + tail if tail else base
    # file = getattr(node.root(), "file", None)
    # file_target = file if file else "<UNKNOWN FILE>"
    # print(f"{' '*4} tracking {target} from {file_target} (count:{c:,})")
    # Cerchiamo a partire dal nodo dove è stato definito il nome base per cercare il tipo che deriva
    #  da esso (tail) o che rappresenta direttamente (se tail è assente)
    assert base is not None

    # print(
    #     f"[DEBUG] Cercando il nome {base}{' da cui origina ' + tail + ' ' if tail else ' '}a partire "
    #     f"dal nodo di tipo {type(node).__name__} e nome {node.name}")

    # Cerca da dove arriva il nome del tipo partendo da questo nodo
    _, type_matches = node.lookup(base)
    # print(f"[DEBUG] {type_matches}")

    if type_matches == () or len(type_matches) > 1:
        # Nessun match o match multipli, quindi non si sa esattamente a che tipo si riferisca il nome.
        # Interrompi subito!
        return None

    type_match_node = type_matches[0]
    # print(f"[DEBUG] Match del tipo {type(type_match_node).__type__}")

    # Controlla il tipo del match per continuare il tracking del tipo
    if isinstance(type_match_node, Import) or \
            isinstance(type_match_node, ImportFrom):
        return utils_handle_type_match_Imports(type_match_node, base, tail, c)
    elif isinstance(type_match_node, ClassDef):
        return utils_handle_type_match_ClassDef(type_match_node, base, tail, c)
    elif isinstance(type_match_node, AssignName):
        return utils_handle_type_match_AssignName(type_match_node, base, tail, c)

    # Il match ottenuto è su un tipo di nodo non previsto per il tracking
    return None


def utils_handle_type_match_Imports(match_node, base, tail, c):
    # Abbiamo uno statement del tipo:
    #  a) >>> import name_1, name_2 as alias_2, name_3, ...
    #  b) >>> from mod_or_pkg import name_1, name_2 as alias_2, name_3, ...
    # La nostra base ha un match con uno dei name o alias presenti nei suddetti statement.

    # Nel caso a) i name sono tutti moduli o packages e stiamo cercando un tipo, ci deve essere
    #  una tail che lo specifica. Nel caso b) stiamo importando da un mod_or_pkg ed i name potrebbero
    #  anche già essere delle classi
    if isinstance(match_node, Import):
        assert tail is not None

    matched_mod_name = None
    new_base = new_tail = None

    if isinstance(match_node, Import):
        # Nel caso a) possiamo importare più packages/moduli con possibile alias
        for mod_name, mod_alias in reversed(match_node.names):
            # Cerchiamo con quale alias o nome coincide la base
            mod_to_cmp = mod_alias if mod_alias else mod_name
            if base == mod_to_cmp:
                matched_mod_name = mod_name
                new_base = tail.split(".")[0]
                new_tail = ".".join(tail.split(".")[1:])
                break
    elif isinstance(match_node, ImportFrom):
        # Nel caso b) abbiamo un package/modulo fisso da cui possiamo importare tutti (*) o più nomi
        #  (rappresentanti packages/moduli/classi/variabili)
        matched_mod_name = match_node.modname

        # Caso di un wildcard from import
        if len(match_node.names) == 1 and match_node.names[0] == ("*", None):
            # Continuare direttamente nel modulo da cui stiamo importando tutto
            new_base = base
            new_tail = tail
        # Normale from import
        else:
            # Cerchiamo con quale alias o nome coincide la base
            for name, alias in reversed(match_node.names):
                name_to_cmp = alias if alias else name
                if base == name_to_cmp:
                    new_base = name
                    new_tail = tail
                    break
    else:
        assert False

    # Lookup ha trovato un match, quindi qualcosa da seguire ci deve essere
    assert matched_mod_name is not None, f"{match_node} ({match_node.lineno})"
    assert new_base is not None

    # Abbiamo quindi un package/modulo da cui partire (matched_mod_name) a cui può seguire una
    #  sequenza di altri packages/moduli/classi che contengono il nostro tipo di interesse,
    #  contenuto nella fine di tail. Quello che dobbiamo fare è trovare l'ultimo package/modulo
    #  che definisce la prima classe.
    #
    # Per esempio:
    #  - matched_mod_name è il package 'pkg_1';
    #  - new_base è il package 'pkg_2';
    #  - new_tail è la sequenza di modulo 'mod_1', classe 'cls_1' e classe innestata finale 'cls_2'.
    # Il nome completo è 'pkg_1.pkg_2.mod_1.cls_1.cls_2'.
    #                                  |-> Questo è quello che vogliamo trovare e importare!
    # Per trovarlo partiamo dalla fine in reverse finché non troviamo un modulo importabile.
    complete_type_name = ".".join([matched_mod_name, new_base] + ([new_tail] if new_tail else []))
    complete_type_name_list = complete_type_name.split(".")
    to_follow_ast = None
    i = 1
    while i < len(complete_type_name_list):
        to_import_mod = ".".join(complete_type_name_list[:-i])
        try:
            to_follow_ast = match_node.do_import_module(to_import_mod)
            break
        except Exception:
            i += 1

    if to_follow_ast:
        j = len(complete_type_name_list) - i
        new_base = ".".join(complete_type_name_list[j:j+1])
        new_tail = ".".join(complete_type_name_list[j+1:])
        return utils_track_type_name(to_follow_ast, new_base, new_tail, c+1)
    return None


def utils_handle_type_match_ClassDef(match_node, base, tail, c):
    if tail:
        # Se c'è una coda a seguire, ci sono classi innestate! Controlliamole ricorsivamente.
        new_base = tail.split(".")[0]
        new_tail = ".".join(tail.split(".")[1:])
        return utils_track_type_name(match_node, new_base, new_tail, c+1)
    else:
        # Se non c'è coda siamo arrivati ad una definizione di classe coincidente col nostro tipo.
        # SUCCESSO!
        assert match_node.name == base
        # Ricostruisci il nome completo del tipo, perso nei vari lookup, risalendo gli scopes
        type_name = base
        complete_type_name = [base]
        scope_node = match_node.parent.scope()
        while type(scope_node) is ClassDef:
            complete_type_name.append(scope_node.name)
            scope_node = scope_node.parent.scope()
        complete_type_name = ".".join(complete_type_name)
        # print(f"[DEBUG] Tipo {type_name} ({complete_type_name}) definito nel modulo {match_node.root().name}")
        return match_node


def utils_handle_type_match_AssignName(match_node, base, tail, c):
    # Abbiamo un assegnamento crea un alias del nostro tipo
    assert isinstance(match_node.parent, Assign)

    # Proviamo a risalire alla vera definizione tramite l'inferenza di astroid, possibile in un
    #  nodo di tipo AssignName
    infers = list(match_node.infer())
    if len(infers) == 1 and isinstance(infers[0], ClassDef):
        # Solo se abbiamo un unico risultato certo che punta ad una classe
        inferred = infers[0]
        # Ricostruisci il nome completo del tipo, perso nei vari lookup, risalendo gli scopes
        type_name = inferred.name
        complete_type_name = [inferred.name]
        scope_node = inferred.parent.scope()
        while type(scope_node) is ClassDef:
            complete_type_name.append(scope_node.name)
            scope_node = scope_node.parent.scope()
        complete_type_name = ".".join(complete_type_name)
        # print(f"[DEBUG] Tipo {type_name} ({complete_type_name}) definito nel modulo {match_node.root().name}")
        return inferred
    return None


def utils_is_static_method(node):
    assert isinstance(node, nodes.FunctionDef)
    decorators_nodes = node.decorators.nodes if node.decorators else []
    decorators_names = [node.name for node in decorators_nodes]
    if "staticmethod" in decorators_names:
        return True
    else:
        return False


def utils_get_self_ref(node):
    # I parametri in ordine sono:
    #  - posonlyargs
    #  - args
    #  - vararg
    #  - kwonlyargs
    #  - kwarg
    assert isinstance(node, nodes.FunctionDef)
    if utils_is_static_method(node):
        return None
    else:
        if node.args.posonlyargs:
            return node.args.posonlyargs[0].name
        else:
            return node.args.args[0].name


def utils_get_anv_list_class(node: nodes.ClassDef):
    # --- 1 Tutti i campi definiti con assegnamento (non annotazione) nel corpo della classe
    assert isinstance(node, nodes.ClassDef)

    # Trova i nomi che si riferiscono a variabili esterne alla classe
    #  (definite da Global, dato che Nonlocal non ha senso in una classe)
    global_names = set()
    for class_body_node in node.get_children():
        if isinstance(class_body_node, nodes.Global):
            for name in class_body_node.names:
                global_names.add(name)

    # Trova i nomi che si riferiscono a campi e potenziali campi della classe dal suo corpo
    for class_body_node in node.get_children():
        # print(f"[DEBUG] {class_body_node}")
        if isinstance(class_body_node, nodes.Assign):
            for target in class_body_node.targets:  # Assegnamenti a catena possibili
                if isinstance(target, nodes.Tuple):
                    for e in target.elts:
                        assert isinstance(e, nodes.AssignName) or isinstance(e, nodes.AssignAttr)
                    names = []
                    for e in target.elts:
                        if isinstance(e, nodes.AssignName) and e.name not in global_names:
                            names.append(e.name)
                        else:
                            assert isinstance(e, nodes.AssignAttr) or e.name in global_names
                            names.append(None)
                    for name in names:
                        if name is not None:
                            # Restituisci solo se almeno un nome è None, se sono tutti None (attributi o globali)
                            #  non restituirla neanche
                            yield (None, names, class_body_node.value, node,)
                            break
                elif isinstance(target, nodes.AssignName):
                    yield (None, target.name, class_body_node.value, node,)
                else:
                    # assert isinstance(target, nodes.AssignAttr), f"{type(target)}"  # TRIGGERED
                    pass
        elif isinstance(class_body_node, nodes.AnnAssign):
            if isinstance(class_body_node.target, nodes.AssignName):
                yield (class_body_node.annotation,
                       class_body_node.target.name,
                       class_body_node.value,
                       node,)
            else:
                assert isinstance(class_body_node.target, nodes.AssignAttr)
                pass


def utils_get_anv_list_constructor(class_node: nodes.ClassDef, constructor_node: nodes.FunctionDef):
    # --- 2 Tutti i campi derivanti dal costruttore
    assert isinstance(class_node, nodes.ClassDef)
    assert isinstance(constructor_node, nodes.FunctionDef) and constructor_node.name == "__init__"

    if not constructor_node.body or utils_is_static_method(constructor_node):
        # Se non c'è body la classe non dichiara __init__ né eredita da altre classi, avendo in mano quindi
        #  il costruttore vuoto di object
        # Implicazione: no attributi derivabili da questo __init__!
        # Note: se per qualche motivo folle il metodo __init__ è statico si cade sempre qui!
        #       Non vi possono essere attributi derivanti dal costruttore se non esiste un "self" a cui riferirsi
        pass
    elif class_node.name == constructor_node.parent.name:
        # Se c'è body ed il padre del costruttore è la stessa classe, il costruttore è
        #  dichiarato esplicitamente nella stessa classe
        # Implicazione: cercare gli attributi nel body!
        # Trovare il parametro usato per riferirsi all'istanza dell'oggetto, solitamente "self" (ma non necessariamente)
        self_ref = utils_get_self_ref(constructor_node)
        assert self_ref

        # ! super().__init__ potrebbe essere chiamato dentro un altro metodo o funzione e fare comunque il suo dovere.
        #   Io controllo solo se chiamato direttamente, poiché le sue potenziali chiamate innestate diventano difficili
        #   da tracciare e sono inverosimili.
        for constructor_body_node in constructor_node.body:
            # print(f"[DEBUG] {constructor_body_node}")
            if isinstance(constructor_body_node, nodes.Assign):
                for target in constructor_body_node.targets:  # Assegnamenti a catena possibili
                    if isinstance(target, nodes.Tuple):
                        for e in target.elts:
                            assert isinstance(e, nodes.AssignName) or isinstance(e, nodes.AssignAttr)
                            if isinstance(e, nodes.AssignAttr):
                                assert isinstance(e.expr, nodes.Name)
                        names = []
                        for e in target.elts:
                            if isinstance(e, nodes.AssignAttr) and e.expr.name == self_ref:
                                names.append(e.attrname)
                            else:
                                assert isinstance(e, nodes.AssignName) or e.expr.name != self_ref
                                names.append(None)
                        for name in names:
                            if name is not None:
                                # Restituisci solo se almeno un nome è None, se sono tutti None (attributi o globali)
                                #  non restituirla neanche
                                yield (None, names, constructor_body_node.value, constructor_body_node,)
                                break
                    elif isinstance(target, nodes.AssignAttr):
                        if isinstance(target.expr, nodes.Name):  # TODO missing other options here
                            if target.expr.name == self_ref:
                                yield (None, target.attrname, constructor_body_node.value, constructor_body_node,)
                    else:
                        # assert isinstance(target, nodes.AssignName), f"{type(target)}" TRIGGERED
                        pass
            elif isinstance(constructor_body_node, nodes.AnnAssign):
                # No tuple negli AnnAssign
                if isinstance(constructor_body_node.target, nodes.AssignAttr):
                    assert isinstance(constructor_body_node.target.expr, nodes.Name)
                    if constructor_body_node.target.expr.name == self_ref:
                        yield (constructor_body_node.annotation,
                               constructor_body_node.target.attrname,
                               constructor_body_node.value,
                               constructor_body_node,)
                else:
                    # assert isinstance(constructor_body_node.target, nodes.AssignAttr)  TRIGGERED
                    pass
            elif isinstance(constructor_body_node, nodes.Expr):
                is_super_constructor_call = False
                parent_constructor_node = None

                is_super_constructor_call = \
                    isinstance(constructor_body_node.value, nodes.Call) and \
                    isinstance(constructor_body_node.value.func, nodes.Attribute) and \
                    constructor_body_node.value.func.attrname == "__init__" and \
                    isinstance(constructor_body_node.value.func.expr, nodes.Call) and \
                    isinstance(constructor_body_node.value.func.expr.func, nodes.Name) and \
                    constructor_body_node.value.func.expr.func.name == "super"

                if is_super_constructor_call:
                    mro = class_node.mro()
                    assert len(mro) > 1  # Se si sta chiamando 'super' qualcuno da cui ereditare c'è!
                    first_parent_node = mro[1]
                    parent_constructor_node = None
                    for method in first_parent_node.methods():
                        assert isinstance(method, nodes.FunctionDef)
                        if method.name == "__init__":
                            parent_constructor_node = method
                            break
                    assert parent_constructor_node
                    yield from utils_get_anv_list_constructor(first_parent_node, parent_constructor_node)
    elif class_node.name != constructor_node.parent.name:
        # Se c'è body ed il padre del costruttore è diverso dalla stessa classe, il costruttore è
        #  uno di quelli delle classi da cui eredita.
        # Implicazione: cercare gli attributi dai genitori!
        pass
    else:
        assert False


def utils_get_anv_list(node: nodes.ClassDef):  # Abbr. di annotation_name_value_list, rinominarlo in atv
    assert isinstance(node, nodes.ClassDef)
    # print(f"[DEBUG] Sono {node.name}")

    # A prescindere una classe prende, esattamente in questo ordine (per i tipi eventuali):
    #  1 Tutti i campi definiti con assegnamento (non annotazione) nel corpo della classe;
    #  2a Se non definisce esplicitamente un __init__, tutti i campi definiti dal primo __init__
    #     ereditato secondo il MRO (method resolution order)
    #  2b Se definisce esplicitamente un __init__, tutti i campi definiti in esso, e se vi è una
    #     chiamata a super() anche quelli dell'__init__ ereditato secondo il MRO

    # Per i tipi facciamo che se è stata lasciata l'annotazione nel corpo della classe li mettiamo,
    #  se il metodo 'infer' ci da un valore di cui possiamo ottenere il tipo lo mettiamo, altrimenti
    #  ciao buona perché non posso impazzire!

    # --- 1 Tutti i campi definiti con assegnamento (non annotazione) nel corpo di questa classe e nel corpo
    #       di tutti i predecessori di ogni grado. Quelli nei genitori vengono sovrascritti però, quindi parti
    #       prima dai predecessori più vecchi fino ai più recenti
    reversed_ancestors_list = reversed(list(node.ancestors()))
    for ancestor in reversed_ancestors_list:
        yield from utils_get_anv_list_class(ancestor)
    yield from utils_get_anv_list_class(node)

    # --- 2 Tutti i campi derivanti dal costruttore di questa classe

    # Trova il nodo associato al costruttore
    constructor_node = None
    for method_node in node.methods():
        if method_node.name =="__init__":
            constructor_node = method_node
            break
    if constructor_node:
        assert constructor_node and isinstance(constructor_node, nodes.FunctionDef), f"{type(constructor_node)}"
        # print(f"[DEBUG] {constructor_node.args}")
        yield from utils_get_anv_list_constructor(node, constructor_node)
