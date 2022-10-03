"""Library CLI definition and execution."""

from argparse import ArgumentParser
from pathlib import Path
import sys
from typing import List


def main(argv: List[str] = None) -> int:
    """Function to be called when the library is executed from the command line.

    Args:
        argv (List[str]): command line arguments, not accounting for the name of the program (first argument).

    Returns:
        int: program exit code.

    """

    parser = get_parser()
    args_dict = vars(parser.parse_args(argv))

    """A 'main' argument from the parser allows to choose the tool that have to be executed. That argument is read to
     run the proper tool accordingly to its predefined interface.
    """
    main_tool = args_dict.pop("tool")
    supported_languages = [file.name for file in Path(__file__).parent.joinpath("rdfization").iterdir()
                           if file.is_dir() and not file.name.startswith("_")]

    if main_tool in supported_languages:
        language = main_tool

        package = f"codeontology.rdfization.{language}.cmd"
        method = "process_args"
        args_process_method = getattr(__import__(package, fromlist=[method]), method)

        if args_process_method(args_dict):
            package = f"codeontology.rdfization.{language}"
            method = "rdfization"
            rdf_extraction_method = getattr(__import__(package, fromlist=[method]), method)
            rdf_extraction_method(**args_dict)
        else:
            # TODO should define proper error codes
            return 1

    return 0


def get_parser() -> ArgumentParser:
    """Get the CLI arguments parser.

    Returns:
        ArgumentParser: the parser.

    """
    from codeontology.rdfization.python3.cmd import define_python3_sub_parser
    # SEE https://docs.python.org/3/library/argparse.html

    # The parser used to present the available main features.
    main_parser = ArgumentParser(
        prog="codeontology",
        description="""
        tool for building and managing knowledge graphs from source code
        """,
        epilog="For more information visit <>",  # TODO Add link to github, where the README gives more info
    )

    # Create and populate the set of sub-parsers from which access the developed features
    features_parsers = main_parser.add_subparsers(
        title="positional arguments",
        description="the main available tools",
        help="available choices",
        dest="tool",
        required=True
    )

    python3_sub_parser = features_parsers.add_parser(
        "python3",
        help="python3 RDF generator",
        description="""
        python3 project source code parsing tool for RDF extraction
        """
    )
    define_python3_sub_parser(python3_sub_parser)

    return main_parser


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
