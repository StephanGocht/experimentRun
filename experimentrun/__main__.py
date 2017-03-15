import argparse
import sys
import os
from . import framework


def loadJson(jsonPath):
    config = framework.loadJson(jsonPath)

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

    sys.path.append(os.path.dirname(args.json))
    framework.bootstrap(loadJson(args.json))


if __name__ == "__main__":
    main()
