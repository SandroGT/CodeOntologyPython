"""Class and methods to visit the AST nodes and extract the related RDF triples."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set, Tuple, Union
from threading import Thread

import astroid
from tqdm import tqdm

from codeontology import LOGGER
from codeontology.ontology import ontology
from codeontology.rdfization.python3.explore import Project
from codeontology.rdfization.python3.extract.individuals import OntologyIndividuals
from codeontology.rdfization.python3.extract.utils import get_parent_node, get_parent_block_node, get_stmt_info,\
    get_prev_statement, get_next_statement


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

        We allow to call `extract` more than once on the same node, because duplicated triples are not a problem, and
         because this way we don't have to check or remember if we previously extracted with linking statements or not.

    """
    project: Project = None
    to_extract: Dict = dict()

    def __init__(self, project: Project):
        Extractor.project = project
        OntologyIndividuals.init_project(project)
        for package in tqdm(list(project.get_packages())):
            t = Thread(target=Extractor.extract_recursively, args=[package.ast, package.ast, True])
            t.start()
            t.join()

    @staticmethod
    def extract_recursively(node: astroid.NodeNG, root_node: astroid.Module, do_link_stmts: bool):
        # Extract from the current node
        Extractor.extract(node, do_link_stmts=do_link_stmts)
        # Check the node upper hierarchy, in case we are visiting an imported node of a referenced module/package,
        #  and we may have not instantiated its package individual.
        current_root: astroid.Module = node.root()
        if node != current_root and root_node != current_root:
            Extractor.extract(current_root, do_link_stmts=False)
            root_node = current_root
        # Check the node lower hierarchy
        for child in node.get_children():
            Extractor.extract_recursively(child, root_node=root_node, do_link_stmts=True)

    @staticmethod
    def extract(node: astroid.NodeNG, do_link_stmts: bool):
        def get_extract_fun_name(_node: astroid.NodeNG) -> str:
            _type_name = type(_node).__name__
            return "extract_" + \
                _type_name[0].lower() + "".join([ch if ch.islower() else "_" + ch.lower() for ch in _type_name[1:]])

        if Extractor.to_extract.get(id(node), None) is None:
            Extractor.to_extract[id(node)] = [True, True]
        to_extract_list = Extractor.to_extract.get(id(node))
        if to_extract_list[int(do_link_stmts)]:
            parent_block_node = get_parent_block_node(node)
            if parent_block_node is not None:
                Extractor.extract(parent_block_node, do_link_stmts=do_link_stmts)
            extract_function_name = get_extract_fun_name(node)
            extract_function = getattr(Extractor, extract_function_name, None)
            if extract_function is not None:
                to_extract_list[int(do_link_stmts)] = False
                extract_function(node, do_link_stmts=do_link_stmts)
            else:
                LOGGER.debug(f"No extraction function available for nodes of type {type(node).__name__}")

    @staticmethod
    def _link_statements(node: astroid.NodeNG, stmt_attr: str = "stmt_individual"):
        assert node.is_statement and hasattr(node, stmt_attr)
        Extractor._link_statements_backward(node, stmt_attr)
        Extractor._link_statements_forward(node, stmt_attr)

    @staticmethod
    def _link_statements_backward(node: astroid.NodeNG, stmt_attr: str):
        assert hasattr(node, stmt_attr)
        if getattr(getattr(node, stmt_attr), "hasPreviousStatement", None) is None:
            prev_node = get_prev_statement(node)
            if prev_node is not None:
                assert prev_node.is_statement

                prev_stmt_individual, prev_stmt_attr = get_stmt_info(prev_node)

                if prev_stmt_individual is not None:
                    getattr(node, stmt_attr).hasPreviousStatement = prev_stmt_individual
                    assert getattr(node, stmt_attr) is prev_stmt_individual.hasNextStatement
                    Extractor._link_statements_backward(prev_node, prev_stmt_attr)

                if prev_stmt_individual is not None and prev_stmt_individual.hasStatementPosition is not None:
                    getattr(node, stmt_attr).hasStatementPosition = prev_stmt_individual.hasStatementPosition + 1
                else:
                    getattr(node, stmt_attr).hasStatementPosition = get_statement_position(node)

            else:
                for node_stmt_individual in [getattr(node, stmt_attr)] + getattr(node, stmt_attr).get_equivalent_to():
                    node_stmt_individual.hasStatementPosition = OntologyIndividuals.START_POSITION_COUNT

    @staticmethod
    def _link_statements_forward(node: astroid.NodeNG, stmt_attr: str):
        assert hasattr(node, stmt_attr)
        if getattr(getattr(node, stmt_attr), "hasNextStatement", None) is None:
            next_node = get_next_statement(node)

            if next_node is not None:
                assert next_node.is_statement

                next_stmt_individual, next_stmt_attr = get_stmt_info(next_node)

                if next_stmt_individual is not None:
                    next_stmt_individual.hasPreviousStatement = getattr(node, stmt_attr)
                    assert next_stmt_individual is getattr(node, stmt_attr).hasNextStatement
                    Extractor._link_statements_forward(next_node, next_stmt_attr)

                if next_stmt_individual is not None and next_stmt_individual.hasStatementPosition is not None:
                    getattr(node, stmt_attr).hasStatementPosition = next_stmt_individual.hasStatementPosition - 1
                else:
                    getattr(node, stmt_attr).hasStatementPosition = get_statement_position(node)

    # TODO Add a general comment about the following methods, so you don't put doc inside every method

    # ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def extract_module(node: astroid.Module, do_link_stmts: bool):
        assert not node.is_statement
        if not hasattr(node, "package_"):
            # Seems that `astroid` doesn't really search for `os.path`, but has its location hardcoded into its code (
            #  function `file_info_from_modpath` from module `modutils.py`), not finding so the `os.path` we downloaded
            #  as Python source code, but the one we have in our python executable that is running this code. We try
            #  here to recover the one we downloaded, and for which we probably have the `package_`. Who knows, maybe
            #  this is useful also for other modules and not only `os.path`.
            for p in Extractor.project.original_sys_path:
                if str(p) in node.file:
                    converted_p = Path(node.file.replace(str(p), str(Extractor.project.python3_path)))
                    if converted_p in Extractor.project.packages:
                        node.package_ = Extractor.project.packages[converted_p]
                        break
        OntologyIndividuals.init_block_statement(node)
        if hasattr(node, "package_"):
            OntologyIndividuals.init_package(node.package_)
            node.package_.individual.hasBody = node.stmt_block_individual
            assert node.package_.individual == node.stmt_block_individual.isBodyOf

    # ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def extract_import(import_node: astroid.Import, do_link_stmts: bool):
        assert import_node.is_statement

        OntologyIndividuals.init_import_statement(import_node)

        if do_link_stmts:
            Extractor._link_statements(import_node)

        for module in import_node.references:
            if module:
                Extractor.extract(module, do_link_stmts=False)
                if hasattr(module, "package_"):
                    import_node.stmt_individual.imports.append(module.package_.individual)
                    assert import_node.stmt_individual in module.package_.individual.isImportedBy

    @staticmethod
    def extract_import_from(import_node: astroid.ImportFrom, do_link_stmts: bool):
        assert import_node.is_statement

        OntologyIndividuals.init_import_statement(import_node)

        if do_link_stmts:
            Extractor._link_statements(import_node)

        for referenced_node in import_node.references:
            if referenced_node is not None:
                assert type(referenced_node) in [
                    astroid.Module,
                    astroid.ClassDef,
                    astroid.FunctionDef, astroid.AsyncFunctionDef,
                    astroid.Assign, astroid.AssignName, astroid.AssignAttr, astroid.AnnAssign
                ], type(referenced_node)
                Extractor.extract(referenced_node, do_link_stmts=False)
                if type(referenced_node) is astroid.Module:
                    if hasattr(referenced_node, "package_"):
                        import_node.stmt_individual.imports.append(referenced_node.package_.individual)
                        assert import_node.stmt_individual in referenced_node.package_.individual.isImportedBy
                elif type(referenced_node) in [astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef]:
                    import_node.stmt_individual.imports.append(referenced_node.individual)
                    assert import_node.stmt_individual in referenced_node.individual.isImportedBy
                elif type(referenced_node) in \
                        [astroid.Assign, astroid.AssignName, astroid.AssignAttr, astroid.AnnAssign]:
                    if hasattr(referenced_node, "var_individual"):
                        import_node.stmt_individual.imports.append(referenced_node.var_individual)
                        assert import_node.stmt_individual in referenced_node.var_individual.isImportedBy
                else:
                    raise NotPredictedClauseException

    # ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def extract_class_def(class_node: astroid.ClassDef, do_link_stmts: bool):
        def get_class_full_name(_class_node: astroid.ClassDef, _module: astroid.Module) -> str:
            scope_hierarchy_names = []
            scope = _class_node.scope()
            while not type(scope) is astroid.Module:
                if type(scope) is astroid.ClassDef:
                    scope_hierarchy_names.insert(0, scope.name)
                else:
                    return ""
                scope = scope.parent.scope()
            return f"{_module.package_.full_name}.{'.'.join(scope_hierarchy_names)}"

        assert class_node.is_statement

        if not hasattr(class_node, "individual"):
            assert not hasattr(class_node, "stmt_individual")

        OntologyIndividuals.init_class(class_node)
        OntologyIndividuals.init_block_statement(class_node)

        class_node.individual.hasBody = class_node.stmt_block_individual
        assert class_node.individual == class_node.stmt_block_individual.isBodyOf

        if do_link_stmts:
            Extractor._link_statements(class_node)

        module = class_node.root()
        Extractor.extract(module, do_link_stmts=False)
        if hasattr(module, "package_"):
            class_node.individual.hasPackage = module.package_.individual
            assert class_node.individual in module.package_.individual.isPackageOf
            class_full_name = get_class_full_name(class_node, module)
            if class_full_name:
                class_node.individual.hasFullyQualifiedName = class_full_name

        if hasattr(class_node, "fields"):
            for field_name in getattr(class_node, "fields"):
                field_type, field_description, field_declaration_node = class_node.fields[field_name]
                # TODO USE field_description
                assert type(field_declaration_node) in [astroid.AssignName, astroid.AssignAttr]

                OntologyIndividuals.init_field(field_name, field_description, field_declaration_node, class_node)
                field_type_individuals = extract_structured_type(field_type)
                access_modifier_individual = get_access_modifier(field_name, field_declaration_node)

                for type_individual in field_type_individuals:
                    field_declaration_node.individual.hasType.append(type_individual)
                    assert field_declaration_node.individual in type_individual.isTypeOf

                field_declaration_node.individual.hasModifier.append(access_modifier_individual)
                assert field_declaration_node.individual in access_modifier_individual.isModifierOf

        for super_class_node in class_node.ancestors(recurs=False):
            Extractor.extract(super_class_node, do_link_stmts=False)
            class_node.individual.extends.append(super_class_node.individual)
            assert class_node.individual in super_class_node.individual.hasSubClass

    # ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def extract_function_def(function_node: Union[astroid.FunctionDef, astroid.AsyncFunctionDef], do_link_stmts: bool):
        assert function_node.is_statement

        if function_node.is_method():
            class_node = get_parent_node(function_node, parent_types={astroid.ClassDef})
            Extractor.extract(class_node, do_link_stmts=False)

        if function_node.is_method() and function_node.name == "__init__":
            # `Constructor`
            OntologyIndividuals.init_constructor(function_node)

            function_node.individual.hasModifier.append(OntologyIndividuals.PUBLIC_ACCESS_MODIFIER)
            assert function_node.individual in OntologyIndividuals.PUBLIC_ACCESS_MODIFIER.isModifierOf

            function_node.individual.isConstructorOf = class_node.individual
            assert function_node.individual in class_node.individual.hasConstructor

        elif function_node.is_method():
            # `Method`
            OntologyIndividuals.init_method(function_node)
            access_modifier_individual = get_access_modifier(function_node.name, function_node)
            if function_node.name.startswith("__") and not function_node.name.endswith("__"):
                assert access_modifier_individual is OntologyIndividuals.PRIVATE_ACCESS_MODIFIER

            function_node.individual.hasModifier.append(access_modifier_individual)
            assert function_node.individual in access_modifier_individual.isModifierOf

            function_node.individual.isMethodOf = class_node.individual
            assert function_node.individual in class_node.individual.hasMethod

            if hasattr(function_node, "overrides"):
                if function_node.overrides is not None:
                    Extractor.extract(function_node.overrides, False)
                    function_node.individual.overrides = function_node.overrides.individual
                    assert function_node.individual in function_node.overrides.individual.isOverriddenBy

        else:
            # `Function`
            OntologyIndividuals.init_function(function_node)

            scope = get_parent_node(function_node,
                                    parent_types={astroid.Module, astroid.FunctionDef, astroid.AsyncFunctionDef})
            if type(scope) is astroid.Module:
                module = scope
                if hasattr(module, "package_"):
                    function_node.individual.hasFullyQualifiedName = \
                        f"{module.package_.full_name}.{function_node.name}"

                    Extractor.extract(module, do_link_stmts=False)
                    function_node.individual.hasPackage = module.package_.individual
                    assert function_node.individual in module.package_.individual.isPackageOf

        if do_link_stmts:
            Extractor._link_statements(function_node)

        if hasattr(function_node, "returns_type"):
            return_type_individuals = extract_structured_type(function_node.returns_type)
            for type_individual in return_type_individuals:
                function_node.individual.hasType.append(type_individual)
                assert function_node.individual in type_individual.isTypeOf

        if hasattr(function_node, "returns_description") and function_node.returns_description is not None:
            function_node.individual.hasDocumentation.append(function_node.returns_description)

    @staticmethod
    def extract_async_function_def(async_function_node: astroid.AsyncFunctionDef, do_link_stmts: bool):
        # They practically are the same, so we just redirect the call
        Extractor.extract_function_def(async_function_node, do_link_stmts=do_link_stmts)

    @staticmethod
    def extract_arguments(args_node: astroid.Arguments, do_link_stmts: bool):
        assert not args_node.is_statement
        executable_node = args_node.parent
        assert type(executable_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef, astroid.Lambda]

        Extractor.extract(executable_node, do_link_stmts=False)

        if not hasattr(args_node, "params_individuals"):
            args_node.params_individuals = []

            if hasattr(args_node, "params"):
                for param_info in args_node.params:
                    param_individual = OntologyIndividuals.init_parameter(*param_info)
                    args_node.params_individuals.append(param_individual)
                    param_type = param_info[2]
                    param_type_individuals = extract_structured_type(param_type)

                    for type_individual in param_type_individuals:
                        param_individual.hasType.append(type_individual)
                        assert param_individual in type_individual.isTypeOf

                    # TODO remove to include lambda
                    if type(executable_node) is not astroid.Lambda:
                        param_individual.isParameterOf = executable_node.individual
                        assert param_individual in executable_node.individual.hasParameter

    @staticmethod
    def extract_decorators(node: astroid.Decorators, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_return(return_node: astroid.Return, do_link_stmts: bool):
        assert return_node.is_statement

        OntologyIndividuals.init_return_statement(return_node)
        function_node = get_parent_node(return_node, {astroid.FunctionDef, astroid.AsyncFunctionDef})
        Extractor.extract(function_node, False)

        if do_link_stmts:
            Extractor._link_statements(return_node)

        return_children = list(return_node.get_children())
        if return_children:
            assert len(return_children) == 1
            expression_node = list(return_node.get_children())[0]
            extract_expression(expression_node)

            return_node.stmt_individual.hasReturnedExpression = expression_node.expr_individual
            assert return_node.stmt_individual == expression_node.expr_individual.isReturnedExpressionOf

        return_node.stmt_individual.isReturnStatementOf = function_node.individual
        assert return_node.stmt_individual in function_node.individual.hasReturnStatement


    @staticmethod
    def extract_yield(node: astroid.Yield, do_link_stmts: bool):
        # Even though `yield` is considered to be a statement
        #  (https://docs.python.org/3/reference/simple_stmts.html#grammar-token-python-grammar-yield_stmt)
        #  these nodes represent `yield expressions`
        #  (https://docs.python.org/3/reference/expressions.html#yieldexpr)
        #  Their parent so are mandatory `expression statements`!
        assert not node.is_statement
        assert node.parent and type(node.parent) is astroid.Expr and node.parent.is_statement

    @staticmethod
    def extract_yield_from(node: astroid.YieldFrom, do_link_stmts: bool):
        # Even though `yield` is considered to be a statement
        #  (https://docs.python.org/3/reference/simple_stmts.html#grammar-token-python-grammar-yield_stmt)
        #  these nodes represent `yield expressions`
        #  (https://docs.python.org/3/reference/expressions.html#yieldexpr)
        #  Their parent so are mandatory `expression statements`!
        assert not node.is_statement
        assert node.parent and type(node.parent) is astroid.Expr and node.parent.is_statement

    # ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def extract_assign(assign_node: Union[astroid.Assign, astroid.AnnAssign, astroid.AugAssign], do_link_stmts: bool):
        assert assign_node.is_statement

        OntologyIndividuals.init_statement(assign_node)
        extract_expression(assign_node)
        extract_left_values(assign_node)

        if assign_node.value is not None:
            assign_node.expr_individual.hasRightHandSide = assign_node.value.expr_individual
            assert assign_node.expr_individual == assign_node.value.expr_individual.isRightHandSideOf
        else:
            assert type(assign_node) is astroid.AnnAssign

        for left_value_individual in assign_node.lv_individuals:
            assign_node.expr_individual.hasLeftHandSide.append(left_value_individual)
            assert assign_node.expr_individual == left_value_individual.isLeftHandSideOf

        if do_link_stmts:
            Extractor._link_statements(assign_node)

    @staticmethod
    def extract_ann_assign(ann_assign_node: astroid.AnnAssign, do_link_stmts: bool):
        assert ann_assign_node.is_statement
        # They practically are the same, so we just redirect the call
        Extractor.extract_assign(ann_assign_node, do_link_stmts=do_link_stmts)

    @staticmethod
    def extract_aug_assign(aug_assign_node: astroid.AugAssign, do_link_stmts: bool):
        assert aug_assign_node.is_statement
        # They practically are the same, so we just redirect the call
        Extractor.extract_assign(aug_assign_node, do_link_stmts=do_link_stmts)

    @staticmethod
    def extract_assign_attr(node: astroid.AssignAttr, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_assign_name(assign_name_node: astroid.AssignName, do_link_stmts: bool):
        assert not assign_name_node.is_statement

        assign_parent_node = get_parent_node(assign_name_node, parent_types={astroid.Assign, astroid.AnnAssign})
        if assign_parent_node is not None:
            Extractor.extract(assign_parent_node, do_link_stmts=do_link_stmts)

    # ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def extract_assert(assert_node: astroid.Assert, do_link_stmts: bool):
        assert assert_node.is_statement

        OntologyIndividuals.init_assert_statement(assert_node)
        assert_children = list(assert_node.get_children())
        assert 1 <= len(assert_children) <= 2
        expression_node = assert_children[0]
        extract_expression(expression_node)

        assert_node.stmt_individual.hasAssertExpression = expression_node.expr_individual
        assert assert_node.stmt_individual == expression_node.expr_individual.isAssertExpressionOf

    # ------------------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def extract_async_for(node: astroid.AsyncFor, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_async_with(node: astroid.AsyncWith, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_attribute(node: astroid.Attribute, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_await(node: astroid.Await, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_bin_op(node: astroid.BinOp, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_bool_op(node: astroid.BoolOp, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_break(break_node: astroid.Break, do_link_stmts: bool):
        assert break_node.is_statement

        OntologyIndividuals.init_break_statement(break_node)

        if do_link_stmts:
            Extractor._link_statements(break_node)

        parent_loop = get_parent_node(break_node, parent_types={astroid.For, astroid.While})
        Extractor.extract(parent_loop, do_link_stmts=False)

        break_node.stmt_individual.hasTargetedBlock = parent_loop.stmt_individual

    @staticmethod
    def extract_call(node: astroid.Call, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_compare(node: astroid.Compare, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_comprehension(node: astroid.Comprehension, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_const(node: astroid.Const, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_continue(continue_node: astroid.Continue, do_link_stmts: bool):
        assert continue_node.is_statement

        OntologyIndividuals.init_continue_statement(continue_node)

        if do_link_stmts:
            Extractor._link_statements(continue_node)

        parent_loop = get_parent_node(continue_node, parent_types={astroid.For, astroid.While})
        Extractor.extract(parent_loop, do_link_stmts=False)

        continue_node.stmt_individual.hasTargetedBlock = parent_loop.stmt_individual

    @staticmethod
    def extract_del_attr(node: astroid.DelAttr, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_del_name(node: astroid.DelName, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_delete(del_node: astroid.Delete, do_link_stmts: bool):
        assert del_node.is_statement

        OntologyIndividuals.init_statement(del_node, stmt_type=ontology.Statement)

        if do_link_stmts:
            Extractor._link_statements(del_node)

    @staticmethod
    def extract_dict(node: astroid.Dict, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_dict_comp(node: astroid.DictComp, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_dict_unpack(node: astroid.DictUnpack, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_ellipsis(node: astroid.Ellipsis, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_empty_node(node: astroid.EmptyNode, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_expr(expr_stmt_node: astroid.Expr, do_link_stmts: bool):
        assert expr_stmt_node.is_statement

        # Retrieve the `Expression` from the `Expression Statement` first
        expr_stmt_children = list(expr_stmt_node.get_children())
        assert len(expr_stmt_children) == 1
        expression_node = expr_stmt_children[0]

        extract_expression(expression_node)
        OntologyIndividuals.init_expression_statement(expr_stmt_node)

        expression_node.expr_individual.isSubExpressionOf = expr_stmt_node.stmt_individual
        assert expression_node.expr_individual in expr_stmt_node.stmt_individual.hasSubExpression

    @staticmethod
    def extract_ext_slice(node: astroid.ExtSlice, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_for(for_node: astroid.For, do_link_stmts: bool):
        assert for_node.is_statement

        OntologyIndividuals.init_for_each_statement(for_node)

        if do_link_stmts:
            Extractor._link_statements(for_node)

        if type(for_node.target) in [astroid.List, astroid.Tuple]:
            variable_nodes = for_node.target.elts
        else:
            variable_nodes = [for_node.target]
        for var_node in variable_nodes:
            if type(var_node) is astroid.AssignName:
                var_individual = extract_variable(var_node)

                if var_individual is not None:  # TODO investigate
                    for_node.stmt_individual.hasForEachVariable.append(var_individual)
                    assert for_node.stmt_individual == var_individual.isForEachVariableOf

        extract_expression(for_node.iter)

        for_node.stmt_individual.hasIterable = for_node.iter.expr_individual
        assert for_node.stmt_individual == for_node.iter.expr_individual.isIterableOf

    @staticmethod
    def extract_formatted_value(node: astroid.FormattedValue, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_generator_exp(node: astroid.GeneratorExp, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_global(global_node: astroid.Global, do_link_stmts: bool):
        assert global_node.is_statement

        OntologyIndividuals.init_statement(global_node, stmt_type=ontology.Statement)

        if do_link_stmts:
            Extractor._link_statements(global_node)

    @staticmethod
    def extract_if(if_node: astroid.If, do_link_stmts: bool):
        assert if_node.is_statement

        OntologyIndividuals.init_if_then_else_statement(if_node)

        if if_node.has_elif_block():
            assert len(if_node.orelse) == 1
            Extractor.extract(if_node.orelse[0], do_link_stmts=True)

            if_node.stmt_individual.hasElseBranch = if_node.orelse[0].stmt_individual
            assert if_node.stmt_individual == if_node.orelse[0].stmt_individual.isElseBranchOf

        extract_expression(if_node.test)
        if_node.stmt_individual.hasCondition = if_node.test.expr_individual
        assert if_node.stmt_individual == if_node.test.expr_individual.isConditionOf

        if do_link_stmts:
            Extractor._link_statements(if_node)

    @staticmethod
    def extract_if_exp(node: astroid.IfExp, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_index(node: astroid.Index, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_joined_str(node: astroid.JoinedStr, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_keyword(node: astroid.Keyword, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_lambda(lambda_node: astroid.Lambda, do_link_stmts: bool):
        assert not lambda_node.is_statement

        OntologyIndividuals.init_lambda_expression(lambda_node)

    @staticmethod
    def extract_list(node: astroid.List, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_list_comp(node: astroid.ListComp, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match(match_node: astroid.Match, do_link_stmts: bool):
        assert match_node.is_statement

        OntologyIndividuals.init_statement(match_node, stmt_type=ontology.Statement)

        if do_link_stmts:
            Extractor._link_statements(match_node)

    @staticmethod
    def extract_match_as(node: astroid.MatchAs, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match_case(node: astroid.MatchCase, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match_class(node: astroid.MatchClass, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match_mapping(node: astroid.MatchMapping, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match_or(node: astroid.MatchOr, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match_sequence(node: astroid.MatchSequence, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match_singleton(node: astroid.MatchSingleton, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match_star(node: astroid.MatchStar, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_match_value(node: astroid.MatchValue, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_name(node: astroid.Name, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_nonlocal(nonlocal_node: astroid.Nonlocal, do_link_stmts: bool):
        assert nonlocal_node.is_statement

        OntologyIndividuals.init_statement(nonlocal_node, stmt_type=ontology.Statement)

        if do_link_stmts:
            Extractor._link_statements(nonlocal_node)

    @staticmethod
    def extract_pass(pass_node: astroid.Pass, do_link_stmts: bool):
        assert pass_node.is_statement

        OntologyIndividuals.init_statement(pass_node, stmt_type=ontology.Statement)

        if do_link_stmts:
            Extractor._link_statements(pass_node)

    @staticmethod
    def extract_raise(raise_node: astroid.Raise, do_link_stmts: bool):
        assert raise_node.is_statement

        OntologyIndividuals.init_statement(raise_node, stmt_type=ontology.ThrowStatement)
        if raise_node.exc is not None:
            extract_expression(raise_node.exc)
            raise_node.stmt_individual.hasThrownExpression = raise_node.exc.expr_individual
            assert raise_node.stmt_individual == raise_node.exc.expr_individual.isThrownExpressionOf

        if do_link_stmts:
            Extractor._link_statements(raise_node)

    @staticmethod
    def extract_set(node: astroid.Set, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_set_comp(node: astroid.SetComp, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_slice(node: astroid.Slice, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_starred(node: astroid.Starred, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_subscript(node: astroid.Subscript, do_link_stmts: bool):
        assert not node.is_statement

    # During parsing a try-except-finally is converted into a try-finally whose try body contains a try-except. This
    #  means that the code:
    #   >>> try:
    #   >>>     pass
    #   >>> except:
    #   >>>     pass
    #   >>> finally:
    #   >>>     pass
    #  Will become:
    #   >>> try:
    #   >>>     try:
    #   >>>         pass
    #   >>>     except:
    #   >>>         pass
    #   >>> finally:
    #   >>>     pass
    # Because of `astroid` the two states are equivalent, and the first one will always become the second one.

    @staticmethod
    def extract_try_except(try_except_node: astroid.TryExcept, do_link_stmts: bool):
        assert try_except_node.is_statement
        OntologyIndividuals.init_try_statement(try_except_node)

        if do_link_stmts:
            Extractor._link_statements(try_except_node, stmt_attr="stmt_try_individual")

    @staticmethod
    def extract_except_handler(except_handler_node: astroid.ExceptHandler, do_link_stmts: bool):
        assert except_handler_node.is_statement
        OntologyIndividuals.init_catch_statement(except_handler_node)
        try_except_node = except_handler_node.parent
        assert type(try_except_node) is astroid.TryExcept
        Extractor.extract(try_except_node, do_link_stmts=False)

        except_handler_node.stmt_individual.isCatchClauseOf = try_except_node.stmt_try_individual
        assert except_handler_node.stmt_individual in try_except_node.stmt_try_individual.hasCatchClause

        if except_handler_node.type is not None:
            if type(except_handler_node.type) is astroid.Tuple:
                _types = except_handler_node.type.elts
            else:
                _types = [except_handler_node.type]
            for _type in _types:
                if type(_type) in [astroid.Name, astroid.Attribute]:
                    if hasattr(_type, "references") and _type.references is not None:
                        _class = _type.references
                        assert type(_class) is astroid.ClassDef
                        Extractor.extract(_type, do_link_stmts=False)
                        except_handler_node.stmt_individual.hasCatchFormalParameter.append(_type.individual)

        if do_link_stmts:
            Extractor._link_statements(except_handler_node)

    @staticmethod
    def extract_try_finally(try_finally_node: astroid.TryFinally, do_link_stmts: bool):
        assert try_finally_node.is_statement

        OntologyIndividuals.init_try_statement(try_finally_node)
        OntologyIndividuals.init_finally_statement(try_finally_node)

        try_finally_node.stmt_try_individual.hasNextStatement = try_finally_node.stmt_finally_individual
        assert try_finally_node.stmt_try_individual == try_finally_node.stmt_finally_individual.hasPreviousStatement
        try_finally_node.stmt_try_individual.hasFinallyClause = try_finally_node.stmt_finally_individual
        assert try_finally_node.stmt_try_individual == try_finally_node.stmt_finally_individual.isFinallyClauseOf

        if do_link_stmts:
            Extractor._link_statements(try_finally_node, stmt_attr="stmt_try_individual")

    @staticmethod
    def extract_tuple(node: astroid.Tuple, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_unary_op(node: astroid.UnaryOp, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_unknown(node: astroid.Unknown, do_link_stmts: bool):
        assert not node.is_statement

    @staticmethod
    def extract_while(while_node: astroid.While, do_link_stmts: bool):
        assert while_node.is_statement

        OntologyIndividuals.init_while_statement(while_node)

        if do_link_stmts:
            Extractor._link_statements(while_node)

        extract_expression(while_node.test)

        while_node.stmt_individual.hasCondition = while_node.test.expr_individual
        assert while_node.stmt_individual == while_node.test.expr_individual.isConditionOf

    @staticmethod
    def extract_with(with_node: astroid.With, do_link_stmts: bool):
        assert with_node.is_statement

        OntologyIndividuals.init_statement(with_node, stmt_type=ontology.Statement)
        OntologyIndividuals.init_block_statement(with_node)

        with_node.stmt_individual.hasBody = with_node.stmt_block_individual
        assert with_node.stmt_individual == with_node.stmt_block_individual.isBodyOf

        if do_link_stmts:
            Extractor._link_statements(with_node)


def extract_structured_type(
        structured_annotation: Union[astroid.ClassDef, List, Tuple, None]
) -> List[Union[ontology.Class, ontology.ParameterizedType, List]]:
    """TODO"""
    def is_all_none(l: list):
        for e in l:
            if type(e) is not type(None):
                return False
        return True

    def extract_structured_type_rec(
            structured_annotation_: Union[astroid.ClassDef, List, Tuple, None]
    ) -> Union[ontology.Class, ontology.ParameterizedType, List, None]:
        type_individual_s = None

        if type(structured_annotation_) is astroid.ClassDef:
            # A single simple type bringing to a `Class` individual (base case)
            Extractor.extract(structured_annotation_, do_link_stmts=False)
            type_individual_s = structured_annotation_.individual
            assert type(type_individual_s) is ontology.Class
        elif type(structured_annotation_) is list:
            # More equivalent types bringing to a list of `Class` or `Parameterized Type` individuals
            for ann_ in structured_annotation_:
                assert type(ann_) in [astroid.ClassDef, tuple, type(None)]
            type_individual_s = [extract_structured_type_rec(ann_) for ann_ in structured_annotation_]
            for individual in type_individual_s:
                assert type(individual) in [ontology.Class, ontology.ParameterizedType, type(None)]
            if is_all_none(type_individual_s):
                type_individual_s = None
        elif type(structured_annotation_) is tuple:
            # A generic type with a parameterization bringing to a `Parameterized Type` individual
            structured_annotation_ = list(structured_annotation_)
            assert type(structured_annotation_[0]) is astroid.ClassDef
            generic_individual = extract_structured_type_rec(structured_annotation_[0])
            assert type(generic_individual) is ontology.Class
            if generic_individual is not None:
                for ann_ in structured_annotation_[1:]:
                    assert type(ann_) in [astroid.ClassDef, list, tuple, type(None)]
                parameterized_individuals = [extract_structured_type_rec(ann_) for ann_ in structured_annotation_[1:]]
                if not is_all_none(parameterized_individuals):
                    type_individual_s = OntologyIndividuals.init_parameterized_type(generic_individual,
                                                                                    parameterized_individuals)
                    assert type(type_individual_s) is ontology.ParameterizedType
                else:
                    type_individual_s = generic_individual
        else:
            assert type(structured_annotation_) is type(None)

        return type_individual_s

    individual = extract_structured_type_rec(structured_annotation)
    if type(individual) is not list:
        if individual is None:
            individual = []
        else:
            individual = [individual]

    return individual


def extract_expression(expression_node: astroid.NodeNG):
    """TODO
    !!! not to be confused with `extract_expr`, that is for `Expression Statement`s (expressions that are not stored or
     used)
     Append the individual to the node as a `individual` attribute
    """
    assert type(expression_node) is not astroid.Expr

    def visit_to_extract_sub_expressions(iter_node: astroid.NodeNG, latest_expression_node: astroid.NodeNG = None):
        """
        TOCOMMENT use this to extract meaningful sub-expressions recursively, lets say only Call and Lambda (we
         cannot have assignments as sub-expressions anyway)"""
        if latest_expression_node is None:
            latest_expression_node = iter_node
        assert hasattr(latest_expression_node, "expr_individual")

        if (iter_node is not latest_expression_node) and (type(iter_node) in [astroid.Call, astroid.Lambda]):
            extract_expression(iter_node)
            latest_expression_node.expr_individual.hasSubExpression.append(iter_node.expr_individual)
            assert latest_expression_node.expr_individual == iter_node.expr_individual.isSubExpressionOf
        else:
            for iter_child_node in iter_node.get_children():
                visit_to_extract_sub_expressions(iter_child_node, latest_expression_node)

    if type(expression_node) in [astroid.Assign, astroid.AnnAssign, astroid.AugAssign]:
        # `Assignment Expression`
        assignment_node: Union[astroid.Assign, astroid.AnnAssign, astroid.AugAssign] = expression_node

        OntologyIndividuals.init_assignment_expression(assignment_node)
        if assignment_node.value is not None:
            extract_expression(assignment_node.value)

            assignment_node.expr_individual.hasSubExpression.append(assignment_node.value.expr_individual)
            assert assignment_node.expr_individual == assignment_node.value.expr_individual.isSubExpressionOf
        else:
            assert type(assignment_node) is astroid.AnnAssign

    elif type(expression_node) is astroid.Call:
        # `Executable Invocation Expression` or `Lambda Invocation Expression`
        # TODO Improve with proper expression creation, distinguishing between the different types of executable and
        #  the lambda too
        OntologyIndividuals.init_executable_invocation_expression(expression_node)
        visit_to_extract_sub_expressions(expression_node)

    elif type(expression_node) is astroid.Lambda:
        # `Lambda Expression`
        OntologyIndividuals.init_lambda_expression(expression_node)
        visit_to_extract_sub_expressions(expression_node)

    # TODO add an elif for astroid.Name so that we can make Variables part of subexpression and try to track their use

    else:
        # Generic `Expression`
        OntologyIndividuals.init_expression(expression_node)
        visit_to_extract_sub_expressions(expression_node)


def extract_left_values(assign_node: Union[astroid.Assign, astroid.AnnAssign, astroid.AugAssign]):
    """TODO append the individual in `lv_individuals`"""
    # TODO extract left values!
    assert type(assign_node) in [astroid.Assign, astroid.AnnAssign, astroid.AugAssign]

    def extract_left_value_from_targets(
            position: int,
            target: Union[astroid.AssignName, astroid.AssignAttr, astroid.Subscript, astroid.List, astroid.Tuple]
    ) -> ontology.LeftValue:
        assert type(target) in [astroid.AssignName, astroid.AssignAttr, astroid.Subscript, astroid.List, astroid.Tuple,
                                astroid.Starred]

        left_value_individual = ontology.LeftValue()
        left_value_individual.hasLeftValuePosition = position

        if type(target) in [astroid.AssignName, astroid.AssignAttr, astroid.Subscript, astroid.Starred]:
            # Base step: we have a variable here
            # NOTE:
            #  astroid.Subscript is for `var[i] = value` and we say treat `var` as the left value;
            #  astroid.Starred is for `first, *middle, last = [v1, v2, v3, v4]` where `middle` is the starred left-value
            #   that gets `[v2, v3]`.
            var_individual = extract_variable(target)
            if var_individual is not None:
                left_value_individual.hasLeftValue.append(var_individual)
        elif type(target) in [astroid.List, astroid.Tuple]:
            # Recursive step
            for j, e in enumerate(target.elts):
                e_individual = extract_left_value_from_targets(j, e)
                left_value_individual.hasLeftValue.append(e_individual)
                assert left_value_individual == e_individual.isLeftValueOf
        return left_value_individual

    if not hasattr(assign_node, "lv_individuals"):
        assign_node.lv_individuals = []

        if type(assign_node) is astroid.Assign:
            targets = assign_node.targets
        else:
            targets = [assign_node.target]

        for i, t in enumerate(targets):
            t_individual = extract_left_value_from_targets(i, t)
            assign_node.lv_individuals.append(t_individual)


def extract_variable(target: Union[astroid.AssignName, astroid.AssignAttr, astroid.Subscript]) -> ontology.Variable:
    """TOCOMMENT resolve a target finding the referenced variable and creating its individual on return"""
    assert type(target) in [astroid.AssignName, astroid.AssignAttr, astroid.Subscript, astroid.Starred]

    if type(target) in [astroid.Subscript, astroid.Starred]:
        var_target = target.value
    else:
        var_target = target

    type_target = None
    if type(target) is astroid.AssignName and type(target.parent) is astroid.AnnAssign:
        if hasattr(target.parent, "structured_annotation"):
            type_target = target.parent.structured_annotation

    var_individual = None
    if hasattr(var_target, "reference"):
        if type(var_target.reference) is astroid.AssignName:
            if not hasattr(var_target.reference, "var_individual"):
                # Discover the variable type
                var_parent_types = {astroid.Module, astroid.ClassDef, astroid.FunctionDef, astroid.AsyncFunctionDef,
                                    astroid.For, astroid.With, astroid.ExceptHandler}
                parent_node = get_parent_node(var_target.reference, parent_types=var_parent_types)
                Extractor.extract(parent_node, do_link_stmts=False)
                if type(parent_node) is astroid.Module:
                    # Global variable
                    OntologyIndividuals.init_global_variable(var_target.reference, parent_node)
                    var_individual = var_target.reference.var_individual
                    if type_target is not None:
                        var_type_individuals = extract_structured_type(type_target)
                        for type_individual in var_type_individuals:
                            var_individual.hasType.append(type_individual)
                            assert var_individual in type_individual.isTypeOf
                elif type(parent_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef] and \
                        parent_node.lineno <= var_target.reference.lineno < parent_node.body[0].lineno:
                    # Function parameter
                    for param_individual in parent_node.args.params_individuals:
                        if param_individual.hasName == var_target.reference.name:
                            var_individual = param_individual
                            break
                    assert var_individual is not None
                elif type(parent_node) in [astroid.FunctionDef, astroid.AsyncFunctionDef,
                                           astroid.For, astroid.With, astroid.ExceptHandler]:
                    # Local variable
                    OntologyIndividuals.init_local_variable(var_target.reference, parent_node)
                    var_individual = var_target.reference.var_individual
                    if type_target is not None:
                        var_type_individuals = extract_structured_type(type_target)
                        for type_individual in var_type_individuals:
                            var_individual.hasType.append(type_individual)
                            assert var_individual in type_individual.isTypeOf
                # TODO Missing `elif type(parent_node) is astroid.ClassDef` for field, that we are not properly tracking yet
            else:
                var_individual = var_target.reference.var_individual

    return var_individual


def get_access_modifier(name: str, ref_node: astroid.NodeNG) -> ontology.AccessModifier:
    """TODO"""
    scope_node = get_parent_node(ref_node)
    if type(scope_node) is astroid.ClassDef:
        if name.startswith("__") and not name.endswith("__"):
            return OntologyIndividuals.PRIVATE_ACCESS_MODIFIER
        elif not name.startswith("__") and name.startswith("_"):
            return OntologyIndividuals.PROTECTED_ACCESS_MODIFIER
    return OntologyIndividuals.PUBLIC_ACCESS_MODIFIER


def get_statement_position(node: astroid.nodes.Statement) -> int:
    """TODO"""
    pos = 0
    iter_node: astroid.nodes.Statement = get_prev_statement(node)
    while iter_node:
        assert isinstance(iter_node, astroid.nodes.Statement) and iter_node.is_statement
        iter_node = get_prev_statement(iter_node)
        if type(iter_node) is astroid.TryFinally:
            pos += 2  # Try + Finally
        elif type(iter_node) is astroid.TryExcept:
            pos += 1 + len(iter_node.handlers)  # Try + Excepts
        else:
            pos += 1

    return OntologyIndividuals.START_POSITION_COUNT + pos


class ExtractionFailingException(Exception):
    pass


class NotPredictedClauseException(ExtractionFailingException):
    pass
