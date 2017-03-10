import argparse
import json
import sys
import os
import re
from . import framework

sys.path.append(os.getcwd())


def removeComments(text):
    """Remove lines starting with //"""
    return re.sub(r"(^|\n)\s*//[^\n]*", "", text)


def loadJson(jsonPath):
    config = None
    with open(jsonPath, 'r') as jsonFile:
        text = removeComments(jsonFile.read())
        try:
            config = json.loads(text)
        except json.JSONDecodeError as e:
            sys.exit("Error in json file %s:%d:%d: %s"
                     % (jsonPath, e.lineno, e.colno, e.msg))

    for key, value in config.items():
        if key == "default_configuration":
            pass
        elif key == "tools":
            pass
        elif key == "configurations":
            if type(value) is not list:
                sys.exit("The entrie for \"configurations\" should be a list, "
                         "i.e. use [{..},{..},..].")
            else:
                pass
        else:
            print("Warning: Ignoring invalid toplevel key: \"%s\"." % (key))
    return config

    # print(json.dumps(data, indent=4))


def main():
    parser = argparse.ArgumentParser(
        description="calculate X to the power of Y")
    parser.add_argument(
        "json",
        help="Json file containing the benchmark configurations.")
    parser.add_argument(
        "-c", "--check", action="store_true", default=False,
        help="check the provided json file")
    args = parser.parse_args()

    framework.bootstrap(loadJson(args.json))


if __name__ == "__main__":
    main()
