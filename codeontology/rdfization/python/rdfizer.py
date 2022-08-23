from codeontology.rdfization.python.explore.explorer import Explorer
from codeontology.rdfization.python.explore.structure import Project, Library, Package
from codeontology.rdfization.python.translate.translator import Translator

def rdfize(
        *,
        to_explore_local_path: str = "",
        to_explore_project_name: str = "",
        to_explore_project_version: str = "",
        recursive: bool = False,
        max_recursions: int = 0,
):
    exp = Explorer(
            to_explore_local_path=to_explore_local_path,
            to_explore_project_name=to_explore_project_name,
            to_explore_project_version=to_explore_project_version,
            recursive=recursive,
            max_recursions=max_recursions
    )
    trl = Translator()
    trl.translate_projects(exp.get_projects())
