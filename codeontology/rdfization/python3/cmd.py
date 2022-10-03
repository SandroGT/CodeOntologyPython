"""CLI definition for the Python3 RDF extraction tool."""

from argparse import ArgumentParser
import os
from pathlib import Path
import shutil
import sys


def define_python3_sub_parser(python3_parser: ArgumentParser):
    """Populates the Python3 argument parser with the options required by its RDF extraction function.

    Args:
        python3_parser (ArgumentParser): a previously created parser for the Python3 language arguments.

    Notes:
        Check the 'codeontology.rdfization.python3.rdfization()' function signature for reference.

    """
    # Common optional arguments, available independently of the input choice.
    common_args_parser = ArgumentParser(add_help=False)
    common_args_parser.add_argument(
        "-o",
        help="""path to the folder in which to store the RDF triples. by default a 'output' folder is created within
        a 'codeontology' folder in the user directory""",
        metavar="OUTPUT",
        type=Path,
        default=None,
        dest="output_dir"
    )
    common_args_parser.add_argument(
        "-d",
        help="""path to the folder in which to store the files to be downloaded. by default a 'download' folder is
        created within a 'codeontology' folder in the user directory""",
        metavar="DOWNLOAD",
        type=Path,
        default=None,
        dest="download_dir"
    )
    common_args_parser.add_argument(
        "--py-exe",
        help="""path to the python3 executable to use to run the download/installation processes, which should be of a
        compatible version according the project specs. by default it is the same python3 executable used to run
        this program""",
        metavar="PY-EXE",
        type=Path,
        default=None,
        dest="python3_exec"
    )
    common_args_parser.add_argument(
        "--py-src",
        help="""path to the python3 standard library source code to refer during parsing. should be the source code of
        the python3 version used as 'executable' (see --py-exec). if not specified, will be automatically downloaded.
        """,
        metavar="PY-SRC",
        type=Path,
        default=None,
        dest="python3_src"
    )

    # Input choices: a name of a project on PyPI or a local project folder.
    # Each of the choices have distinctive options.
    input_parser = python3_parser.add_subparsers(
        title="positional arguments",
        description="the main available choices for providing the input",
        help="available choices",
        dest="input_type",
        required=True
    )

    path_parser = input_parser.add_parser(
        "local",
        help="""a local project folder""",
        parents=[common_args_parser]
    )
    path_parser.add_argument(
        help="""the path to the folder containing the project source code and setup files""",
        metavar="FOLDER",
        type=Path,
        dest="project_path"
    )
    path_parser.add_argument(
        "--pkgs",
        help="""the path to the folder containing all the files/folders for the top level packages of the project
        distribution. if not specified it will be automatically retrieved from the project setup info. has to be
        specified along with the '--deps' option. useful to speed up and avoid installation/download operations""",
        metavar="PKGS",
        type=Path,
        default=None,
        dest="project_pkgs"
    )
    path_parser.add_argument(
        "--deps",
        help="""the path to the folder containing all the files/folders for the top level packages of the project
        dependencies. if not specified it will be automatically retrieved from the project setup info. has to be
        specified along with the '--pkgs' option. useful to speed up and avoid installation/download operations""",
        metavar="DEPS",
        type=Path,
        default=None,
        dest="project_deps"
    )

    name_parser = input_parser.add_parser(
        "pypi",
        help="""a remote project on PyPI""",
        parents=[common_args_parser]
    )
    name_parser.add_argument(
        help="""the package reference on PyPI, such as <name> or <name>==<version> for a specific version""",
        metavar="TARGET",
        type=str,
        dest="pypi_target"
    )


def process_args(args: dict) -> int:
    """Processes the arguments returned by the Python3 arguments parser.

    Prepares the dictionary for the call of the RDF extraction function: checks for inconsistencies, remove unnecessary
     options, sets default values.

    Args:
        args (dict): the dictionary of args as returned by the parser, that will be modified.

    Returns:
        bool: `True` if no problems occurred, `False` otherwise.

    Notes:
        Check the 'codeontology.rdfization.python3.rdfization()' function signature for reference.
        For the arguments specifying folders, the validity of their content is not checked. Just their existence!

    """
    import codeontology
    user_dir: Path = Path(os.path.expanduser("~")).absolute()
    codeontology_folder: Path = user_dir.joinpath("codeontology")

    # Input type dependant arguments
    input_type = args.pop("input_type")
    if input_type == "local":

        project_path: Path = args.get("project_path")
        if not project_path.exists() or not project_path.is_dir():
            print("argument 'FOLDER' is not a valid existent folder", file=sys.stderr)
            return False

        project_pkgs: Path = args.get("project_pkgs", None)
        project_deps: Path = args.get("project_deps", None)
        if bool(project_pkgs) ^ bool(project_deps):
            # xor, so `True` if only one key/element is present (none or both are accepted)
            print("'--pkgs' and '--deps' must be provided together", file=sys.stderr)
            return False
        if project_pkgs and project_deps:
            if not project_pkgs.exists() or not project_pkgs.is_dir():
                print("argument 'PKGS' is not a valid existent folder", file=sys.stderr)
                return False
            if not project_deps.exists() or not project_deps.is_dir():
                print("argument 'DEPS' is not a valid existent folder", file=sys.stderr)
                return False

    # Common arguments
    output_dir: Path = args.get("output_dir")
    if output_dir:
        if not output_dir.exists():
            output_dir.mkdir()
        elif not output_dir.is_dir():
            print("argument 'OUTPUT' is not a valid existent folder", file=sys.stderr)
            return False
    else:
        if not codeontology_folder.exists():
            codeontology_folder.mkdir()
        output_dir = codeontology_folder.joinpath("output")
        if not output_dir.exists():
            output_dir.mkdir()
        args["output_dir"] = output_dir

    download_dir: Path = args.get("download_dir")
    if download_dir:
        if not download_dir.exists():
            download_dir.mkdir()
        elif not download_dir.is_dir():
            print("argument 'DOWNLOAD' is not a valid existent folder", file=sys.stderr)
            return False
    else:
        if not codeontology_folder.exists():
            codeontology_folder.mkdir()
        download_dir = codeontology_folder.joinpath("download")
        if not download_dir.exists():
             download_dir.mkdir()
        args["download_dir"] = download_dir

    python3_exec: Path = args.get("python3_exec")
    if python3_exec:
        if not python3_exec.exists() or not python3_exec.is_file():
            print("argument 'PY-EXE' cannot be a valid python3 executable", file=sys.stderr)
            return False
    else:
        args["python3_exec"] = Path(sys.executable)

    python3_src: Path = args.get("python3_src")
    if python3_src:
        if not python3_src.exists() or not python3_src.is_dir():
            print("argument 'PY-SRC' is not a valid existent folder", file=sys.stderr)
            return False

    return True
