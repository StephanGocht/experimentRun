import pymysql
import argparse
import sys
import os
import logging
import traceback
import time
from experimentrun import framework
from experimentrun import json_names
from copy import copy


configTemplate = """
{
    // workgroup this instance will pull entries from
    "workgroup":"",
    // prefix to tables in the database
    "prefix": "",
    // database credentials
    "server": {
        "host"     : "",
        "user"     : "",
        "password" : "",
        "db"       : "",
        "charset"  : "utf8",
    }
}
"""


def main():
    parser = argparse.ArgumentParser(
        description="Run benchmarks")
    parser.add_argument(
        "json",
        help="Json file containing the database configurations, use -t to get a template.",
        nargs='?')
    parser.add_argument(
        "-b", "--batchmode", action="store_false", default=True,
        help="Disables batchmode, i.e. no longer ignores errors with loaded configs.")
    parser.add_argument(
        "-t", "--template", action="store_true", default=False,
        help="Display a template of the json used for configuration.")
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

    if args.template:
        print(configTemplate)
        exit()
    elif args.json == None:
        parser.print_usage()
        print("error: json is a required argument unless -t is used to display the template for it.")
        exit()

    for include in args.include:
        framework.includes.append(os.path.abspath(include))
    sys.path.extend(framework.includes)

    config = framework.loadJson(args.json)
    service = DBService.fromConfig(config)
    dispatcher = MysqlWorklistDispatcher(service)
    dispatcher.run(batchmode = args.batchmode)

    # service.addItem("abisko", "/home/asdf.json")
    # work = service.aquireWorkItem("abisko")
    # service.doneWorkItem(work["id"])


def addQuery(prefix):
    return  """
            INSERT into `{}worklist` (workgroup, config_file)
            values (%(workgroup)s, %(config_file)s);
        """.format((prefix))

def selectQuery(prefix):
    return  """
            SELECT id, config_file
            from `{}worklist`
            where workgroup = %(workgroup)s
                and state = 'open'
            limit 1
            for update;
        """.format((prefix))

def updateQuery(prefix):
    return  """
            UPDATE `{}worklist`
            SET state = 'processing', aquired = now()
            WHERE id = %(id)s;
        """.format((prefix))

def doneQuery(prefix):
    return  """
            UPDATE `{}worklist`
            SET state = 'done'
            WHERE id = %(id)s;
        """.format((prefix))

def errorQuery(prefix):
    return  """
            UPDATE `{}worklist`
            SET state = 'error'
            WHERE id = %(id)s;
        """.format((prefix))

def retry(func):
    def func_wrapper(*args, **kwargs):
        service = args[0]

        if service.credentials is not None:
            try:
                return func(*args, **kwargs)
            except pymysql.err.Error:
                pass

            # Did you try closing and opening the connection again?
            if service.connection.open:
                service.connection.close()
            service.connection = pymysql.connect(
                cursorclass=pymysql.cursors.DictCursor,
                **service.credentials)

        return func(*args, **kwargs)

    return func_wrapper

class DBService:
    @classmethod
    def fromConfig(cls, config):
        connection = pymysql.connect(
            cursorclass=pymysql.cursors.DictCursor,
            **config["server"])

        return cls(connection, config["prefix"], config["workgroup"], config["server"])

    def __init__(self, connection, prefix, workgroup, credentials = None):
        self.connection = connection
        self.prefix = prefix
        self.workgroup = workgroup
        self.credentials = credentials

    @retry
    def doneWorkItem(self, id):
        with self.connection.cursor() as cursor:
            cursor.execute(
                doneQuery(self.prefix),
                {'id': id})
            self.connection.commit()

    @retry
    def errorWorkItem(self, id):
        with self.connection.cursor() as cursor:
            cursor.execute(
                errorQuery(self.prefix),
                {'id': id})
            self.connection.commit()

    @retry
    def aquireWorkItem(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                selectQuery(self.prefix),
                {'workgroup': self.workgroup})
            selected = cursor.fetchall()

            result = None
            if len(selected) > 0:
                result = selected[0]

                cursor.execute(
                    updateQuery(self.prefix),
                    {'id': selected[0]["id"]})

                self.connection.commit()

            return result

    @retry
    def addItem(self, config_file):
        with self.connection.cursor() as cursor:
            cursor.execute(
                addQuery(self.prefix),
                {'workgroup': self.workgroup, 'config_file': config_file})
            self.connection.commit()

class MysqlWorklistDispatcher:
    def __init__(self, dbservice):
        self.service = dbservice

    def run(self, batchmode = True):
        while True:
            item = self.service.aquireWorkItem()
            if item == None:
                break

            path = item["config_file"]
            dirname = os.path.dirname(path)

            origSysPath = copy(sys.path)
            origIncludes = copy(framework.includes)
            framework.includes.append(dirname)
            sys.path.append(dirname)

            print(path)
            try:
                config = framework.loadJson(path)
                config[json_names.exrunConfDir.text] = str(dirname)
                framework.bootstrap(config, path)

                self.service.doneWorkItem(item["id"])
            except Exception as e:
                self.service.errorWorkItem(item["id"])
                if not batchmode:
                    raise e
                else:
                    traceback.print_exc()

            framework.includes = origIncludes
            sys.path = origSysPath




if __name__ == '__main__':
    main()