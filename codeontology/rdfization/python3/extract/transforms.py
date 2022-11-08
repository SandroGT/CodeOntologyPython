"""Transform functions on AST nodes to increase their expressiveness."""

import astroid


class Transformer:
    """A collection of methods to integrate the information carried by the AST nodes of 'astroid'."""

    @staticmethod
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
            ancestors_mro = node.parent.mro()[1:]  # First in method resolution order (mro) is the parent class itself
            for ancestor_node in ancestors_mro:
                for ancestor_method_node in ancestor_node.methods():
                    # In Python methods are identified just by their names, there is no "overloading"
                    if ancestor_method_node.name == node.name:
                        # Set and terminate search
                        node.overrides = ancestor_method_node
                        return

    @staticmethod
    def add_args_type(node: astroid.Arguments):
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

    @staticmethod
    def add_expression_type(node: Expr):
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
    def add_class_fields(node: astroid.ClassDef):
        """Adds a new field `TODO` to represent all the recognized fields/attributes/class variables of the class.

        The fields of a class in Python can only be determined with certainty at runtime, but we can try to predict at
         least the most obvious field by looking at the assignments (but not deletions) to the class object itself in
         constructor methods.

        Args:
            node (astroid.ClassDef): a node representing a class definition and body.

        """
        assert isinstance(node, astroid.ClassDef)
        from transforms_utils import resolve_annotation

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
