import argparse
import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from experimentrun import framework
from experimentrun import json_names


def main():
    parser = argparse.ArgumentParser(
        description="Run benchmarks")
    parser.add_argument(
        "json",
        help="Json file containing the benchmark configurations.")
    parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        '-v', '--verbose',
        help="Be verbose",
        action="store_const", dest="loglevel", const=logging.INFO,
    )
    parser.add_argument(
        '-I', '--include',
        action="append",
        help='List of folders to add to path.',
        default=list()
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    try:
        framework.exrun(args.json, args.include)
    except Exception as e:
        logging.warn("Ups, it seems like something went wrong. Pleas check the error output, if it doesn't help you can use -d to get debug output including a trace.")
        if (args.loglevel == logging.DEBUG):
            raise e


if __name__ == "__main__":
    main()
