"""Class and methods to visit the AST nodes and extract the related RDF triples."""

from __future__ import annotations

import astroid

from codeontology.rdfization.python3.explore import Project, Library, Package
from codeontology.rdfization.python3.extract.individuals import Individuals
from codeontology.utils import pass_on_exception


class Extractor:
    """A collection of methods for the operations to perform on different types of AST nodes.

    Notes:
        We extract everything from the Project packages. We then extract individuals of the referenced things in
         referenced modules/packages/libraries. We do not extract individuals from a library that was indicated as a
         dependency if it is never referenced. Additionally, if only a class is used from a package, we will not extract
         all its content, but we will create the individual for the package and the one for the class, along with all
         the class content, but not with all the module content.
        ??? We could add a parameter for the extraction, that allows someone to say he wants to extract everything from
         the indicated dependency libraries too... this could be done easily by extending the for in the __init__ from
         the only packages in the project to the packages in the dependencies too! Since the project contains as
         dependencies the dependencies of the direct dependencies, we will extract everything for sure! (at least, for
         what it is available).

        When we instantiate a property between individuals, `owlready2` automatically creates the inverse property if
         existent. Just as an example, if we instantiate a (hypothetical) `dependsOn` property, the correspondent
         `isDependentFrom` property will be automatically created.

    """

    def __init__(self, project: Project):
        Individuals.init_project(project)
        for package in project.get_packages():
            Extractor._extract_recursively(package.ast, package.ast, True)

    @staticmethod
    def _extract_recursively(node: astroid.NodeNG, root_node: astroid.Module, do_link_stmts: bool):
        # Extract from the current node
        Extractor._extract(node, do_link_stmts)
        # Check the node upper hierarchy, in case we are visiting an imported node of a referenced module/package,
        #  and we may have not instantiated its package individual.
        current_root: astroid.Module = node.root()
        if node != current_root and root_node != current_root:
            Extractor._extract_module(current_root, False)
            root_node = current_root
        # Check the node lower hierarchy
        for child in node.get_children():
            Extractor._extract_recursively(child, root_node, True)

    @staticmethod
    def _extract(node: astroid.NodeNG, do_link_stmts: bool):
        def get_extract_fun_name(_node: astroid.NodeNG) -> str:
            _type_name = type(_node).__name__
            return "_extract_" + \
                   _type_name[0].lower() + "".join([ch if ch.islower() else "_" + ch.lower() for ch in _type_name[1:]])

        extract_function_name = get_extract_fun_name(node)
        extract_function = getattr(Extractor, extract_function_name, None)
        assert extract_function is not None
        extract_function(node, do_link_stmts)

    @staticmethod
    def _link_stmts(node: astroid.NodeNG):
        assert node.is_statement and getattr(node, "stmt_individual", NonExistent) is not NonExistent
        if node.previous_sibling():
            # !!! We are extracting and linking statements only from scopes we are visiting in their entirety: in that
            #  case AST nodes are visited sequentially, so we always pass through the previous node first, for which
            #  the "statement individual" should then exists!
            prev = node.previous_sibling()
            assert prev.is_statement
            # !!! TODO Convert to assert once all the statements are extracted
            if getattr(prev, "stmt_individual", NonExistent) is not NonExistent:
                node.stmt_individual.hasPreviousStatement = prev.stmt_individual

    # TODO Add a general comment about the following methods, so you don't put doc inside every method

    @staticmethod
    def _extract_ann_assign(node: astroid.AnnAssign, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_arguments(node: astroid.Arguments, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_assert(node: astroid.Assert, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_assign(node: astroid.Assign, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_assign_attr(node: astroid.AssignAttr, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_assign_name(node: astroid.AssignName, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_async_for(node: astroid.AsyncFor, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_async_function_def(node: astroid.AsyncFunctionDef, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_async_with(node: astroid.AsyncWith, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_attribute(node: astroid.Attribute, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_aug_assign(node: astroid.AugAssign, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_await(node: astroid.Await, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_bin_op(node: astroid.BinOp, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_bool_op(node: astroid.BoolOp, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_break(node: astroid.Break, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_call(node: astroid.Call, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_class_def(class_node: astroid.ClassDef, do_link_stmts: bool):
        def get_class_full_name(_class_node: astroid.ClassDef, _module: astroid.Module) -> str:
            scope_hierarchy_names = []
            scope = _class_node.scope()
            while not isinstance(scope, astroid.Module):
                if isinstance(scope, astroid.ClassDef):
                    scope_hierarchy_names.insert(0, scope.name)
                else:
                    return ""
                scope = scope.parent.scope()
            return f"{_module._package.full_name}.{'.'.join(scope_hierarchy_names)}"

        assert class_node.is_statement

        Individuals.init_class(class_node)
        Individuals.init_declaration_statement(class_node)

        if do_link_stmts:
            Extractor._link_stmts(class_node)

        class_node.stmt_individual.declares.append(class_node.individual)

        module = class_node.root()
        Extractor._extract_module(module, False)
        if getattr(module, "_package", NonExistent) is not NonExistent:
            class_node.individual.hasPackage = module._package.individual
            class_full_name = get_class_full_name(class_node, module)
            if class_full_name:
                class_node.individual.hasFullyQualifiedName = class_full_name

        for field_name in getattr(class_node, "fields", {}):
            field_type, field_declaration_node = class_node.fields[field_name]
            # !!! TODO Create Field individuals
            pass

        for super_class_node in class_node.ancestors(recurs=False):
            Extractor._extract_class_def(super_class_node, do_link_stmts=False)
            class_node.individual.extends.append(super_class_node.individual)

    @staticmethod
    def _extract_compare(node: astroid.Compare, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_comprehension(node: astroid.Comprehension, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_const(node: astroid.Const, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_continue(node: astroid.Continue, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_decorators(node: astroid.Decorators, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_del_attr(node: astroid.DelAttr, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_del_name(node: astroid.DelName, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_delete(node: astroid.Delete, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_dict(node: astroid.Dict, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_dict_comp(node: astroid.DictComp, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_dict_unpack(node: astroid.DictUnpack, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_ellipsis(node: astroid.Ellipsis, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_empty_node(node: astroid.EmptyNode, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_except_handler(node: astroid.ExceptHandler, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_expr(node: astroid.Expr, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_ext_slice(node: astroid.ExtSlice, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_for(node: astroid.For, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_formatted_value(node: astroid.FormattedValue, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_function_def(node: astroid.FunctionDef, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_generator_exp(node: astroid.GeneratorExp, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_global(node: astroid.Global, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_if(node: astroid.If, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_if_exp(node: astroid.IfExp, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_import(import_node: astroid.Import, do_link_stmts: bool):
        assert import_node.is_statement

        Individuals.init_import_statement(import_node)

        if do_link_stmts:
            Extractor._link_stmts(import_node)

        for module in import_node.references:
            if module:
                Extractor._extract_module(module, False)
                if getattr(module, "_package", NonExistent) is not NonExistent:
                    import_node.stmt_individual.imports.append(module._package.individual)

    @staticmethod
    def _extract_import_from(import_node: astroid.ImportFrom, do_link_stmts: bool):
        assert import_node.is_statement

        Individuals.init_import_statement(import_node)

        if do_link_stmts:
            Extractor._link_stmts(import_node)

        for references in import_node.references:
            if references is not None:
                for referenced_node in references:
                    if referenced_node is None:
                        continue
                    assert type(referenced_node) in [
                        astroid.Module,
                        astroid.ClassDef,
                        astroid.FunctionDef, astroid.AsyncFunctionDef,
                        astroid.Assign, astroid.AssignName, astroid.AssignAttr, astroid.AnnAssign
                    ]
                    Extractor._extract(referenced_node, False)
                    if type(referenced_node) in [astroid.Module]:
                        if getattr(referenced_node, "_package", NonExistent) is not NonExistent:
                            import_node.stmt_individual.imports.append(referenced_node._package.individual)
                    elif type(referenced_node) in [astroid.ClassDef]:
                        # TODO INIT
                        pass
                    elif type(referenced_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef]:
                        # TODO INIT
                        pass
                    elif type(referenced_node) in \
                            [astroid.Assign, astroid.AssignName, astroid.AssignAttr, astroid.AnnAssign]:
                        # TODO INIT
                        pass

    @staticmethod
    def _extract_index(node: astroid.Index, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_joined_str(node: astroid.JoinedStr, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_keyword(node: astroid.Keyword, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_lambda(node: astroid.Lambda, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_list(node: astroid.List, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_list_comp(node: astroid.ListComp, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match(node: astroid.Match, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_as(node: astroid.MatchAs, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_case(node: astroid.MatchCase, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_class(node: astroid.MatchClass, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_mapping(node: astroid.MatchMapping, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_or(node: astroid.MatchOr, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_sequence(node: astroid.MatchSequence, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_singleton(node: astroid.MatchSingleton, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_star(node: astroid.MatchStar, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_match_value(node: astroid.MatchValue, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_module(node: astroid.Module, do_link_stmts: bool):
        assert not node.is_statement
        if getattr(node, "_package", NonExistent) is not NonExistent:
            Individuals.init_package(node._package)

    @staticmethod
    def _extract_name(node: astroid.Name, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_nonlocal(node: astroid.Nonlocal, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_pass(node: astroid.Pass, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_raise(node: astroid.Raise, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_return(node: astroid.Return, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_set(node: astroid.Set, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_set_comp(node: astroid.SetComp, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_slice(node: astroid.Slice, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_starred(node: astroid.Starred, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_subscript(node: astroid.Subscript, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_try_except(node: astroid.TryExcept, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_try_finally(node: astroid.TryFinally, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_tuple(node: astroid.Tuple, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_unary_op(node: astroid.UnaryOp, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_unknown(node: astroid.Unknown, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_while(node: astroid.While, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_with(node: astroid.With, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_yield(node: astroid.Yield, do_link_stmts: bool):
        pass

    @staticmethod
    def _extract_yield_from(node: astroid.YieldFrom, do_link_stmts: bool):
        pass


class NonExistent:
    pass
