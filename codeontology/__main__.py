""""""
# SEE https://docs.python.org/3/library/argparse.html


import argparse
import pathlib  # SEE https://docs.python.org/3/library/pathlib.html
import sys
import textwrap
from typing import List


def get_parser() -> argparse.ArgumentParser:
    top_parser = argparse.ArgumentParser(
        prog="codeontology",
        description=textwrap.dedent("""
        Describe me here in a looong way
        """),
        epilog="For more information visit <>.",  # TODO Add link to github, where the README gives more info
    )

    sub_parsers = top_parser.add_subparsers(
        title="languages",
        description="desc",
        help="parsable language options",
        dest="language"
    )

    define_python_parser(sub_parsers.add_parser(
        "python",
        help="short description",
        description="long description",
    ))

    return top_parser


def define_python_parser(python_parser: argparse.ArgumentParser):

    input_group = python_parser.add_mutually_exclusive_group(required=True)

    input_group.add_argument(
        "-p", "--path",
        type=pathlib.Path,
    )

    input_group.add_argument(
        "-n", "--name",
        type=str
    )

    python_parser.add_argument(
        "-o", "--output",
        type=pathlib.Path,
        dest="output_path"
    )

    python_parser.add_argument(
        "-e", "--executable",
        type=pathlib.Path
    )


def main(argv: List[str] = None):
    parser = get_parser()
    answer = parser.parse_args(argv)
    # then do something with answer
    print(answer)


if __name__ == "__main__":
    main(sys.argv[1:])
