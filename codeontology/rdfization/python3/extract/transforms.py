"""Transform functions on AST nodes to increase their expressiveness.

TODO total revision and refactoring needed.
"""

import astroid


class Transformer:

    @staticmethod
    def transform_add_method_overrides(node: astroid.FunctionDef):
        """
        Add to a node of type 'astroid.FunctionDef' a tuple linking to the method node it is overriding and its class node
         owner in a 'overrides' attribute. Contains '(None, None)' if it overrides nothing.
        """
        # print("transform_add_method_overrides")
        assert isinstance(node, astroid.FunctionDef)
        overridden_method_node = class_owner_node = None
        if isinstance(node.parent, astroid.ClassDef):
            ancestors_mro = node.parent.mro()[1:]  # first ancestor is itself, skip it
            for ancestor_node in ancestors_mro:
                for ancestor_method_node in ancestor_node.methods():
                    if ancestor_method_node.name == node.name:
                        overridden_method_node = ancestor_method_node
                        class_owner_node = ancestor_node
                        break
                if overridden_method_node:
                    break
        node.overrides = (overridden_method_node, class_owner_node)

    @staticmethod
    def transform_add_method_args_type(node: astroid.FunctionDef):
        """
        Add to a node of type 'astroid.FunctionDef' a link to the nodes defining the types of
        """
        # print("transform_add_method_args_type")
        assert isinstance(node, astroid.FunctionDef)
        arguments: astroid.Arguments = node.args
        assert isinstance(arguments, astroid.Arguments)

        def convert(built_type):
            if built_type is None:
                return None
            elif isinstance(built_type, str):
                # print(f"from {node.name} ({node.root().file}) search for {built_type}")
                return utils_lookup_type_name(node, built_type)
            elif isinstance(built_type, list):
                return [convert(b) for b in built_type]
            else:
                assert isinstance(built_type, tuple), f"{built_type} ({type(built_type)})"
                return tuple([convert(b) for b in built_type])

        class_annotations = []
        # print(f"Line {node.lineno} in {node.root().file}:\n{' '*4}{arguments.annotations}")
        for ann in arguments.annotations:
            class_ann = None
            try:
                built_type = utils_build_type_annotation(ann)
                if built_type:
                    class_ann = convert(built_type)
            except Exception:
                pass
            class_annotations.append(class_ann)
        # print(f"{' '*4}{class_annotations}")
        arguments.class_annotations = class_annotations
        assert isinstance(getattr(arguments, "class_annotations"), list)

    @staticmethod
    def transform_add_expression_type(node: astroid.Expr):
        assert isinstance(node, astroid.Expr)
        class_type = None
        try:
            infers = node.value.inferred()
        except Exception:
            infers = []
        assert isinstance(infers, list)
        if len(infers) == 1:  # Solo risposte certe
            inferred_value = infers[0]
            if inferred_value is not astroid.Uninferable:
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
                    class_type = utils_lookup_type_name(scope, inferred_type)
                except Exception:
                    pass
        node.class_type = class_type

    @staticmethod
    def transforms_add_class_fields(node: astroid.nodes.ClassDef):
        assert isinstance(node, astroid.nodes.ClassDef)
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
                    built_type = utils_build_type_annotation(annotation)
                except Exception:
                    built_type = None
                fields_dict[target] = (built_type, value, def_node)

        node.fields_dict = fields_dict


def utils_build_type_annotation(ann):
    """
    Restituisce una stringa, una tupla o una lista:
     - a) una stringa indica un tipo non parametrico, o di cui non sono stati specificati tipi che lo parametrizzano;
     - b) se si ottiene una lista vuol dire che più tipi equivalenti sono ammessi, ed è coinvolto l'operatore di unione
          (union types) nell'annotazione;
     - c) una tupla indica la presenza di tipi parametrici, dove il primo elemento della tupla è una stringa che indica
          il tipo parametrico, e ogni elemento a seguire è uno dei tipi che lo parametrizzano, rappresentato
          ricorsivamente come descritto (quindi può essere una stringa, una lista o una tupla).

    Tuple[List[str], Tuple[int, int] | float | Exception] | List

    [(Tuple, (List, str), [(Tuple, int, int), float, exception]), List]
    """
    # print(f"[DEBUG] {ann}")
    if ann is None:
        return None
    # --- a) stringa
    if isinstance(ann, astroid.Name):
        # Direttamente il tipo, come 'str'
        return ann.name
    elif isinstance(ann, astroid.Attribute):
        # Il tipo è dentro un modulo o una classe, come 'typing.List'
        name = [ann.attrname]
        ann = ann.expr
        while isinstance(ann, astroid.Attribute):
            name.insert(0, ann.attrname)
            ann = ann.expr
        assert isinstance(ann, astroid.Name)
        name.insert(0, ann.name)
        return ".".join(name)
    elif isinstance(ann, astroid.Const):
        # Il tipo è rappresentato tramite una stringa, e la stringa stessa rappresenta il tipo
        if isinstance(ann.value, str):
            return ann.value
        elif isinstance(ann.value, type(Ellipsis)):
            return "Any"
        elif ann.value is None:
            return None
        else:
            assert False, f"{ann.value} ({type(ann.value)})"
    # --- b) lista
    elif isinstance(ann, astroid.BinOp):
        # Il tipo è una unione di tipi, per esempio "int | float"
        equivalent_types = []
        while isinstance(ann, astroid.BinOp):
            assert ann.op == "|"
            equivalent_types.insert(0, ann.right)
            ann = ann.left
        equivalent_types.insert(0, ann)
        return [utils_build_type_annotation(ann_type) for ann_type in equivalent_types]
    # --- c) tupla
    elif isinstance(ann, astroid.Subscript):
        # Il tipo è una composizione che coinvolge le parentesi quadre, come "List[]"
        type_ = [utils_build_type_annotation(ann.value)]
        type_built = utils_build_type_annotation(ann.slice)
        if isinstance(type_built, str):
            type_params = [type_built]
        else:
            assert isinstance(type_built, list) or isinstance(type_built, tuple)
            type_params = list(type_built)
        return tuple(type_ + type_params)
    elif isinstance(ann, astroid.Tuple) or isinstance(ann, astroid.List):
        # Il tipo è una composizione che coinvolge un elenco separato da virgole, per esempio "[int, float]"
        assert isinstance(ann.elts, list)
        return [utils_build_type_annotation(e) for e in ann.elts]
    # end
    else:
        assert False, f"{type(ann)}"


def utils_lookup_type_name(node, name):
    assert isinstance(name, str) and len(name) > 0
    base = name.split(".")[0]
    tail = ".".join(name.split(".")[1:])
    return utils_track_type_name(node, base, tail)


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
    if isinstance(type_match_node, astroid.Import) or \
            isinstance(type_match_node, astroid.ImportFrom):
        return utils_handle_type_match_Imports(type_match_node, base, tail, c)
    elif isinstance(type_match_node, astroid.ClassDef):
        return utils_handle_type_match_ClassDef(type_match_node, base, tail, c)
    elif isinstance(type_match_node, astroid.AssignName):
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
    if isinstance(match_node, astroid.Import):
        assert tail is not None

    matched_mod_name = None
    new_base = new_tail = None

    if isinstance(match_node, astroid.Import):
        # Nel caso a) possiamo importare più packages/moduli con possibile alias
        for mod_name, mod_alias in reversed(match_node.names):
            # Cerchiamo con quale alias o nome coincide la base
            mod_to_cmp = mod_alias if mod_alias else mod_name
            if base == mod_to_cmp:
                matched_mod_name = mod_name
                new_base = tail.split(".")[0]
                new_tail = ".".join(tail.split(".")[1:])
                break
    elif isinstance(match_node, astroid.ImportFrom):
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
        while type(scope_node) is astroid.ClassDef:
            complete_type_name.append(scope_node.name)
            scope_node = scope_node.parent.scope()
        complete_type_name = ".".join(complete_type_name)
        # print(f"[DEBUG] Tipo {type_name} ({complete_type_name}) definito nel modulo {match_node.root().name}")
        return match_node


def utils_handle_type_match_AssignName(match_node, base, tail, c):
    # Abbiamo un assegnamento crea un alias del nostro tipo
    assert isinstance(match_node.parent, astroid.Assign)

    # Proviamo a risalire alla vera definizione tramite l'inferenza di astroid, possibile in un
    #  nodo di tipo astroid.AssignName
    infers = list(match_node.infer())
    if len(infers) == 1 and isinstance(infers[0], astroid.ClassDef):
        # Solo se abbiamo un unico risultato certo che punta ad una classe
        inferred = infers[0]
        # Ricostruisci il nome completo del tipo, perso nei vari lookup, risalendo gli scopes
        type_name = inferred.name
        complete_type_name = [inferred.name]
        scope_node = inferred.parent.scope()
        while type(scope_node) is astroid.ClassDef:
            complete_type_name.append(scope_node.name)
            scope_node = scope_node.parent.scope()
        complete_type_name = ".".join(complete_type_name)
        # print(f"[DEBUG] Tipo {type_name} ({complete_type_name}) definito nel modulo {match_node.root().name}")
        return inferred
    return None


def utils_is_static_method(node):
    assert isinstance(node, astroid.nodes.FunctionDef)
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
    assert isinstance(node, astroid.nodes.FunctionDef)
    if utils_is_static_method(node):
        return None
    else:
        if node.args.posonlyargs:
            return node.args.posonlyargs[0].name
        else:
            return node.args.args[0].name


def utils_get_anv_list_class(node: astroid.nodes.ClassDef):
    # --- 1 Tutti i campi definiti con assegnamento (non annotazione) nel corpo della classe
    assert isinstance(node, astroid.nodes.ClassDef)

    # Trova i nomi che si riferiscono a variabili esterne alla classe
    #  (definite da Global, dato che Nonlocal non ha senso in una classe)
    global_names = set()
    for class_body_node in node.get_children():
        if isinstance(class_body_node, astroid.nodes.Global):
            for name in class_body_node.names:
                global_names.add(name)

    # Trova i nomi che si riferiscono a campi e potenziali campi della classe dal suo corpo
    for class_body_node in node.get_children():
        # print(f"[DEBUG] {class_body_node}")
        if isinstance(class_body_node, astroid.nodes.Assign):
            for target in class_body_node.targets:  # Assegnamenti a catena possibili
                if isinstance(target, astroid.nodes.Tuple):
                    for e in target.elts:
                        assert isinstance(e, astroid.nodes.AssignName) or isinstance(e, astroid.nodes.AssignAttr)
                    names = []
                    for e in target.elts:
                        if isinstance(e, astroid.nodes.AssignName) and e.name not in global_names:
                            names.append(e.name)
                        else:
                            assert isinstance(e, astroid.nodes.AssignAttr) or e.name in global_names
                            names.append(None)
                    for name in names:
                        if name is not None:
                            # Restituisci solo se almeno un nome è None, se sono tutti None (attributi o globali)
                            #  non restituirla neanche
                            yield (None, names, class_body_node.value, node,)
                            break
                elif isinstance(target, astroid.nodes.AssignName):
                    yield (None, target.name, class_body_node.value, node,)
                else:
                    # assert isinstance(target, astroid.nodes.AssignAttr), f"{type(target)}"  # TRIGGERED
                    pass
        elif isinstance(class_body_node, astroid.nodes.AnnAssign):
            if isinstance(class_body_node.target, astroid.nodes.AssignName):
                yield (class_body_node.annotation,
                       class_body_node.target.name,
                       class_body_node.value,
                       node,)
            else:
                assert isinstance(class_body_node.target, astroid.nodes.AssignAttr)
                pass


def utils_get_anv_list_constructor(class_node: astroid.nodes.ClassDef, constructor_node: astroid.nodes.FunctionDef):
    # --- 2 Tutti i campi derivanti dal costruttore
    assert isinstance(class_node, astroid.nodes.ClassDef)
    assert isinstance(constructor_node, astroid.nodes.FunctionDef) and constructor_node.name == "__init__"

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
            if isinstance(constructor_body_node, astroid.nodes.Assign):
                for target in constructor_body_node.targets:  # Assegnamenti a catena possibili
                    if isinstance(target, astroid.nodes.Tuple):
                        for e in target.elts:
                            assert isinstance(e, astroid.nodes.AssignName) or isinstance(e, astroid.nodes.AssignAttr)
                            if isinstance(e, astroid.nodes.AssignAttr):
                                assert isinstance(e.expr, astroid.nodes.Name)
                        names = []
                        for e in target.elts:
                            if isinstance(e, astroid.nodes.AssignAttr) and e.expr.name == self_ref:
                                names.append(e.attrname)
                            else:
                                assert isinstance(e, astroid.nodes.AssignName) or e.expr.name != self_ref
                                names.append(None)
                        for name in names:
                            if name is not None:
                                # Restituisci solo se almeno un nome è None, se sono tutti None (attributi o globali)
                                #  non restituirla neanche
                                yield (None, names, constructor_body_node.value, constructor_body_node,)
                                break
                    elif isinstance(target, astroid.nodes.AssignAttr):
                        if isinstance(target.expr, astroid.nodes.Name):  # TODO missing other options here
                            if target.expr.name == self_ref:
                                yield (None, target.attrname, constructor_body_node.value, constructor_body_node,)
                    else:
                        # assert isinstance(target, astroid.nodes.AssignName), f"{type(target)}" TRIGGERED
                        pass
            elif isinstance(constructor_body_node, astroid.nodes.AnnAssign):
                # No tuple negli AnnAssign
                if isinstance(constructor_body_node.target, astroid.nodes.AssignAttr):
                    assert isinstance(constructor_body_node.target.expr, astroid.nodes.Name)
                    if constructor_body_node.target.expr.name == self_ref:
                        yield (constructor_body_node.annotation,
                               constructor_body_node.target.attrname,
                               constructor_body_node.value,
                               constructor_body_node,)
                else:
                    # assert isinstance(constructor_body_node.target, astroid.nodes.AssignAttr)  TRIGGERED
                    pass
            elif isinstance(constructor_body_node, astroid.nodes.Expr):
                is_super_constructor_call = False
                parent_constructor_node = None

                is_super_constructor_call = \
                    isinstance(constructor_body_node.value, astroid.nodes.Call) and \
                    isinstance(constructor_body_node.value.func, astroid.nodes.Attribute) and \
                    constructor_body_node.value.func.attrname == "__init__" and \
                    isinstance(constructor_body_node.value.func.expr, astroid.nodes.Call) and \
                    isinstance(constructor_body_node.value.func.expr.func, astroid.nodes.Name) and \
                    constructor_body_node.value.func.expr.func.name == "super"

                if is_super_constructor_call:
                    mro = class_node.mro()
                    assert len(mro) > 1  # Se si sta chiamando 'super' qualcuno da cui ereditare c'è!
                    first_parent_node = mro[1]
                    parent_constructor_node = None
                    for method in first_parent_node.methods():
                        assert isinstance(method, astroid.nodes.FunctionDef)
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


def utils_get_anv_list(node: astroid.nodes.ClassDef):  # Abbr. di annotation_name_value_list, rinominarlo in atv
    assert isinstance(node, astroid.nodes.ClassDef)
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
        assert constructor_node and isinstance(constructor_node, astroid.nodes.FunctionDef), f"{type(constructor_node)}"
        # print(f"[DEBUG] {constructor_node.args}")
        yield from utils_get_anv_list_constructor(node, constructor_node)
