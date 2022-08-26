from codeontology.rdfization.python import global_pypi
from codeontology.rdfization.python.explore.structure import Project


class Explorer:
    _to_explore_project_name: str
    _to_explore_project_version: str = "",
    _root_download_abs_path: str

    _to_translate: Project

    def __init__(
            self,
            to_explore_project_name: str,
            to_explore_project_version: str = "",
    ):
        # Check input
        if not global_pypi.is_existing_project(to_explore_project_name, to_explore_project_version):
            target_name = f"{to_explore_project_name}" + \
                          f"=={to_explore_project_version}" if to_explore_project_version else ""
            raise Exception(f"Unknown project {target_name} on PyPI index")

        # --- Init ---
        self._to_explore_project_name = to_explore_project_name
        self._to_explore_project_version = to_explore_project_version

        download_target, abs_project_path, abs_install_path, installed_packages = global_pypi.download_project(
            self._to_explore_project_name,
            self._to_explore_project_version
        )

        self._to_translate = Project(download_target, abs_project_path, abs_install_path, installed_packages)

    def get_project(self) -> Project:
        return self._to_translate
