import argparse
from experimentrun import framework
from experimentrun.dispatcher.mysql_worklist import DBService
import logging
from contextlib import closing
import sys
import os

def main():
    parser = argparse.ArgumentParser(
        description="Run benchmarks")
    parser.add_argument(
        "json",
        help="Json file containing the database configurations, use -t to get a template.")

    parser.add_argument(
        "-p",
        "--prefix",
        help="Prefix to add to every line.",
        )

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

    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    config = framework.loadJson(args.json)

    with DBService.fromConfig(config) as service:
        for line in sys.stdin:
            file = os.path.join(os.path.dirname(line), "problem.json")
            if (args.prefix is not None):
                file = os.path.join(args.prefix, file)
            service.resetWorkItemByFile(file)

if __name__ == '__main__':
    main()