"""Python3 tool for RDF triples extraction."""

from pathlib import Path


def rdfization(*, project_path: Path = None, project_pkgs: Path = None, project_deps: Path = None,
               pypi_target: str = None, output_dir: Path = None, download_dir: Path = None, python3_exec: Path = None,
               python3_src: Path = None):
    """The function to be called to start the RDF triples extraction for a Python3 project.

    Args:
        project_path (Path): the path to the folder containing the project source.
        project_pkgs (Path): the path to the folder containing the top level packages paths of the project distribution.
        project_deps (Path): the path to the folder containing the top level packages paths of the project dependencies.
        pypi_target (str): the name of the project in the index, eventually with the specific version, such as in
         '<project_name>' or '<project_name>==<version>' (using the 'version matching' clause, '==').
        output_dir (Path): the path to the folder in which to store the output RDF triples.
        download_dir (Path): the path to the folder in which to download the needed files.
        python3_exec (Path): the path to a locally installed 'Python3 executable', used to run 'pip' functionalities.
        python3_src (Path): the path to the folder containing the Python3 standard library source code.

    """
    # NOTE in-library imports should stay here inside the function, or they will be executed before calling the
    #  function, for example, triggering the loading of the base ontology before even running the command parser
    from codeontology import logger
    from codeontology.ontology import ontology
    from codeontology.rdfization.python3.explore import Project
    from codeontology.rdfization.python3.extract.serializer import Serializer
    from codeontology.rdfization.python3.explore_utils import ProjectHandler, PySourceHandler

    # Retrieve project files
    assert output_dir and download_dir and python3_exec
    project_handler = ProjectHandler(python3_exec)
    py_source_handler = PySourceHandler()

    # If a project on PyPI has been specified, download it locally
    if pypi_target:
        assert not project_path and not project_pkgs and not project_deps
        project_path = project_handler.download_source_from_pypi(pypi_target, download_dir)

    # Install the local project, if necessary
    if not project_pkgs and not project_deps:
        install_dir = download_dir.joinpath("install")
        project_name, project_pkgs, project_deps = project_handler.install_local_project(project_path, install_dir)
    else:
        project_name = project_handler.get_local_project_name(project_path)

    # Get the Python source if necessary
    if not python3_src:
        py_version = py_source_handler.get_py_executable_version(python3_exec)
        python3_src = py_source_handler.download_python_source(py_version, download_dir)

    # Reconstruct the project structure
    project = Project(project_name, project_path, project_pkgs, project_deps, python3_src)

    # Extract the triples from the project structure
    # !!! The ontology is global, triples will be stored there automatically! That's why there is no need for a object
    #  return or ontology parameter. This should be solved, since I don't like having a global ontology!
    Serializer(project)

    # Store everything
    save_file = str(output_dir.joinpath(project_name+".nt"))
    logger.info(f"Saving triples at '{save_file}'.")
    ontology.save(save_file, format="ntriples")
