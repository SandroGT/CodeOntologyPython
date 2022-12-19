"""Class and methods to visit the AST nodes and extract the related RDF triples."""

from __future__ import annotations

import astroid

from codeontology.rdfization.python3.explore import Project, Library, Package
from codeontology.rdfization.python3.extract.individuals import Individuals


class Extractor:
    """A collection of methods for the operations to perform on different types of AST nodes."""

    def __init__(self, project: Project):
        Individuals.init_project(project)
        for package in project.get_packages():
            Extractor._visit_to_extract(package.ast, package.ast)

    @staticmethod
    def _visit_to_extract(node: astroid.NodeNG, root_node: astroid.Module):
        # Extract from the current node
        extract_function_name = Extractor._get_extract_fun_name(node)
        extract_function = getattr(Extractor, extract_function_name, None)
        assert extract_function is not None
        extract_function(node)
        # Check the node upper hierarchy, in case we are extracting from a node of a referenced library, we want to
        #  extract the infos from its module too
        current_root: astroid.Module = node.root()
        if current_root != root_node:
            Extractor._extract_module(current_root)
            root_node = current_root
        # Check the node lower hierarchy
        for child in node.get_children():
            Extractor._visit_to_extract(child, root_node)

    @staticmethod
    def _get_extract_fun_name(cls_node: astroid.NodeNG) -> str:
        cls_name = type(cls_node).__name__
        return "_extract_" + \
               cls_name[0].lower() + "".join([ch if ch.islower() else "_"+ch.lower() for ch in cls_name[1:]])

    # TODO Add a comment about following methods

    @staticmethod
    def _extract_ann_assign(node: astroid.AnnAssign):
        pass

    @staticmethod
    def _extract_arguments(node: astroid.Arguments):
        pass

    @staticmethod
    def _extract_assert(node: astroid.Assert):
        pass

    @staticmethod
    def _extract_assign(node: astroid.Assign):
        pass

    @staticmethod
    def _extract_assign_attr(node: astroid.AssignAttr):
        pass

    @staticmethod
    def _extract_assign_name(node: astroid.AssignName):
        pass

    @staticmethod
    def _extract_async_for(node: astroid.AsyncFor):
        pass

    @staticmethod
    def _extract_async_function_def(node: astroid.AsyncFunctionDef):
        pass

    @staticmethod
    def _extract_async_with(node: astroid.AsyncWith):
        pass

    @staticmethod
    def _extract_attribute(node: astroid.Attribute):
        pass

    @staticmethod
    def _extract_aug_assign(node: astroid.AugAssign):
        pass

    @staticmethod
    def _extract_await(node: astroid.Await):
        pass

    @staticmethod
    def _extract_bin_op(node: astroid.BinOp):
        pass

    @staticmethod
    def _extract_bool_op(node: astroid.BoolOp):
        pass

    @staticmethod
    def _extract_break(node: astroid.Break):
        pass

    @staticmethod
    def _extract_call(node: astroid.Call):
        pass

    @staticmethod
    def _extract_class_def(node: astroid.ClassDef):
        pass

    @staticmethod
    def _extract_compare(node: astroid.Compare):
        pass

    @staticmethod
    def _extract_comprehension(node: astroid.Comprehension):
        pass

    @staticmethod
    def _extract_const(node: astroid.Const):
        pass

    @staticmethod
    def _extract_continue(node: astroid.Continue):
        pass

    @staticmethod
    def _extract_decorators(node: astroid.Decorators):
        pass

    @staticmethod
    def _extract_del_attr(node: astroid.DelAttr):
        pass

    @staticmethod
    def _extract_del_name(node: astroid.DelName):
        pass

    @staticmethod
    def _extract_delete(node: astroid.Delete):
        pass

    @staticmethod
    def _extract_dict(node: astroid.Dict):
        pass

    @staticmethod
    def _extract_dict_comp(node: astroid.DictComp):
        pass

    @staticmethod
    def _extract_dict_unpack(node: astroid.DictUnpack):
        pass

    @staticmethod
    def _extract_ellipsis(node: astroid.Ellipsis):
        pass

    @staticmethod
    def _extract_empty_node(node: astroid.EmptyNode):
        pass

    @staticmethod
    def _extract_except_handler(node: astroid.ExceptHandler):
        pass

    @staticmethod
    def _extract_expr(node: astroid.Expr):
        pass

    @staticmethod
    def _extract_ext_slice(node: astroid.ExtSlice):
        pass

    @staticmethod
    def _extract_for(node: astroid.For):
        pass

    @staticmethod
    def _extract_formatted_value(node: astroid.FormattedValue):
        pass

    @staticmethod
    def _extract_function_def(node: astroid.FunctionDef):
        pass

    @staticmethod
    def _extract_generator_exp(node: astroid.GeneratorExp):
        pass

    @staticmethod
    def _extract_global(node: astroid.Global):
        pass

    @staticmethod
    def _extract_if(node: astroid.If):
        pass

    @staticmethod
    def _extract_if_exp(node: astroid.IfExp):
        pass

    @staticmethod
    def _extract_import(node: astroid.Import):
        # `import` works with modules/packages, not their content
        assert node.is_statement
        Individuals.init_import_statement(node)  # TODO should connect statements with next and previous. How?
        # !!! now node.individual exists
        for name, alias in node.names:
            try:
                module: astroid.Module = node.do_import_module(name)
                Extractor._extract_module(module)
                if getattr(module, "package", NonExistent) is not NonExistent:
                    node.individual.imports.append(module.package.individual)
            except Exception:
                pass

    @staticmethod
    def _extract_import_from(node: astroid.ImportFrom):
        assert node.is_statement
        Individuals.init_import_statement(node)  # TODO should connect statements with next and previous. How?
        # `from import` works with the content of modules/packages, so other modules/packages, but also classes,
        #  functions or global variables
        for name, alias in node.names:
            if name != "*":
                # We have not a wildcard import, we have to discover the nature of what we are importing: is it a
                #  module/package or not?
                try:
                    module = node.do_import_module(f"{node.modname}.{name}")
                    # If we arrive here, it was a module/package
                    Extractor._extract_module(module)
                    if getattr(module, "package", NonExistent) is not NonExistent:
                        node.individual.imports.append(module.package.individual)
                except Exception:
                    # If we arrive raising the Exception, it was not a module/package, but a class, function or global
                    #  variable
                    try:
                        imported = node.do_import_module(f"{node.modname}")
                        _, matches = imported.lookup(name)
                        # !!! If we statically find a correspondence with more than one object/declaration, which
                        #  dynamically is likely to be uniquely resolved, we link to all correspondences, all of which
                        #  may be valid. Think about conditional definitions for OS-dependent implementations.
                        for object in matches:
                            if isinstance(object, astroid.ClassDef):
                                pass
                            if isinstance(object, astroid.FunctionDef):
                                pass
                            if type(object) in [astroid.Assign, astroid.AssignName, astroid.AssignAttr, astroid.AnnAssign]:
                                pass
                            if type(object) in [astroid.Import, astroid.ImportFrom]:
                                pass
                            # TODO init the imported object (class, function, variable) to link it as imported by the
                            #  statement. But it could be something recursively coming from an import!
                    except Exception:
                        pass
            else:
                # We have a wildcard import, so we are importing all the content from a module/package
                try:
                    module = node.do_import_module(f"{node.modname}")
                    # !!! I should not extract all the module content, only imported things... expressions do not count!
                    Extractor._visit_to_extract(module, module)
                    for child in module.get_children():
                        # TODO connect child individual to import if it is a global variable, function or class. I
                        #  think also recursively imported names are to account for
                        # !!! I could leverage the individual that at this step will be on the nodes! Like, the imports
                        #  have all the imported individuals as elements of the property `imports`. We just have to
                        #  check the nature of the node... this could need too much work maybe
                        # Optional imports (inside an if)? Just ignore them, I should predict the if clause otherwise.
                        pass
                except Exception:
                    pass

    @staticmethod
    def _extract_index(node: astroid.Index):
        pass

    @staticmethod
    def _extract_joined_str(node: astroid.JoinedStr):
        pass

    @staticmethod
    def _extract_keyword(node: astroid.Keyword):
        pass

    @staticmethod
    def _extract_lambda(node: astroid.Lambda):
        pass

    @staticmethod
    def _extract_list(node: astroid.List):
        pass

    @staticmethod
    def _extract_list_comp(node: astroid.ListComp):
        pass

    @staticmethod
    def _extract_match(node: astroid.Match):
        pass

    @staticmethod
    def _extract_match_as(node: astroid.MatchAs):
        pass

    @staticmethod
    def _extract_match_case(node: astroid.MatchCase):
        pass

    @staticmethod
    def _extract_match_class(node: astroid.MatchClass):
        pass

    @staticmethod
    def _extract_match_mapping(node: astroid.MatchMapping):
        pass

    @staticmethod
    def _extract_match_or(node: astroid.MatchOr):
        pass

    @staticmethod
    def _extract_match_sequence(node: astroid.MatchSequence):
        pass

    @staticmethod
    def _extract_match_singleton(node: astroid.MatchSingleton):
        pass

    @staticmethod
    def _extract_match_star(node: astroid.MatchStar):
        pass

    @staticmethod
    def _extract_match_value(node: astroid.MatchValue):
        pass

    @staticmethod
    def _extract_module(node: astroid.Module):
        if getattr(node, "package", NonExistent) is not NonExistent:
            Individuals.init_package(node.package)

    @staticmethod
    def _extract_name(node: astroid.Name):
        pass

    @staticmethod
    def _extract_nonlocal(node: astroid.Nonlocal):
        pass

    @staticmethod
    def _extract_pass(node: astroid.Pass):
        pass

    @staticmethod
    def _extract_raise(node: astroid.Raise):
        pass

    @staticmethod
    def _extract_return(node: astroid.Return):
        pass

    @staticmethod
    def _extract_set(node: astroid.Set):
        pass

    @staticmethod
    def _extract_set_comp(node: astroid.SetComp):
        pass

    @staticmethod
    def _extract_slice(node: astroid.Slice):
        pass

    @staticmethod
    def _extract_starred(node: astroid.Starred):
        pass

    @staticmethod
    def _extract_subscript(node: astroid.Subscript):
        pass

    @staticmethod
    def _extract_try_except(node: astroid.TryExcept):
        pass

    @staticmethod
    def _extract_try_finally(node: astroid.TryFinally):
        pass

    @staticmethod
    def _extract_tuple(node: astroid.Tuple):
        pass

    @staticmethod
    def _extract_unary_op(node: astroid.UnaryOp):
        pass

    @staticmethod
    def _extract_unknown(node: astroid.Unknown):
        pass

    @staticmethod
    def _extract_while(node: astroid.While):
        pass

    @staticmethod
    def _extract_with(node: astroid.With):
        pass

    @staticmethod
    def _extract_yield(node: astroid.Yield):
        pass

    @staticmethod
    def _extract_yield_from(node: astroid.YieldFrom):
        pass


class NonExistent:
    pass
