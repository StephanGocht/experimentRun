import argparse
import sys
import os
import logging
from . import framework


def main():
    parser = argparse.ArgumentParser(
        description="Run benchmarks")
    parser.add_argument(
        "json",
        help="Json file containing the benchmark configurations.")
    parser.add_argument(
        "-c", "--check", action="store_true", default=False,
        help="check the provided json file")
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

    framework.includes.append(os.path.dirname(args.json))
    for include in args.include:
        framework.includes.append(os.path.abspath(include))

    sys.path.extend(framework.includes)
    framework.bootstrap(framework.loadJson(args.json))


if __name__ == "__main__":
    main()
