from codeontology.rdfization.python.explore.explorer import Explorer
from codeontology.rdfization.python.explore.structure import Project, Library, Package
from codeontology.rdfization.python.translate.translator import Translator

def rdfize(
        to_explore_project_name: str,
        to_explore_project_version: str = "",
):
    exp = Explorer(to_explore_project_name, to_explore_project_version)
    trl = Translator(exp.get_project())
