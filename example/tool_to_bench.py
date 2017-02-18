"""
This is an example tool to be benchmarked that prints all arguments.
"""

import sys


def main():
    for arg in sys.argv:
        print(arg)


if __name__ == "__main__":
    main()
