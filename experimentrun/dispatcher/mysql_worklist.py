import pymysql
import argparse
import sys
import os
import logging
import traceback
import time
import random
import socket
from contextlib import closing
from experimentrun import framework
from experimentrun.tools import BlockedExceptionDuringRun
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
    dispatcher = MysqlWorklistDispatcher(config)
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

def resetQueryByFile(prefix):
    return  """
            UPDATE `{}worklist`
            SET state = 'open'
            WHERE config_file = %(file)s;
        """.format((prefix))


def openConnection(credentials, batchmode):
    connection = None
    tries = 0
    while (connection is None):
        try:
            tries += 1
            connection = pymysql.connect(
                cursorclass=pymysql.cursors.DictCursor,
                **credentials)
        except pymysql.err.Error as e:
            if (batchmode == False) or (tries > 15):
                raise
            else:
                # lets sleep a random amount, so we most likely prevent
                # conflicts in the future when hitting the mysql max
                # connection limit
                logging.warning("Could not connect to databse ["+str(e)+"]. Trying again.")
                time.sleep(random.randrange(1,120) / 2)

    return connection

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
            service.connection = openConnection(service.credentials, batchmode = True)

        return func(*args, **kwargs)

    return func_wrapper

class DBService:
    @classmethod
    def fromConfig(cls, config, batchmode = False):
        return closing(cls(openConnection(config["server"], batchmode), config["prefix"], config["workgroup"], config["server"]))

    @classmethod
    def fromConfigNc(cls, config, batchmode = False):
        return cls(openConnection(config["server"], batchmode), config["prefix"], config["workgroup"], config["server"])

    def __init__(self, connection, prefix, workgroup, credentials = None):
        self.connection = connection
        self.prefix = prefix
        self.workgroup = workgroup
        self.credentials = credentials

    def close(self):
        if self.connection.open:
            self.connection.close()

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

    @retry
    def resetWorkItemByFile(self, file):
        with self.connection.cursor() as cursor:
            cursor.execute(
                resetQueryByFile(self.prefix),
                {'file': file})
            self.connection.commit()

class MysqlWorklistDispatcher:
    def __init__(self, dbconfig):
        self.dbconfig = dbconfig

    def run(self, batchmode = True):
        print("Running on: " + socket.gethostname())
        numErrors = 0

        item = None
        with DBService.fromConfig(self.dbconfig, batchmode) as service:
            item = service.aquireWorkItem()

        while item != None and numErrors < 30:
            path = item["config_file"]
            dirname = os.path.dirname(path)

            origSysPath = copy(sys.path)
            origIncludes = copy(framework.includes)
            framework.includes.append(dirname)
            sys.path.append(dirname)

            print("Working on: %s" % (path))

            error = False
            try:
                config = framework.loadJson(path)
                config[json_names.exrunConfDir.text] = str(dirname)
                framework.bootstrap(config, path)
            except BlockedExceptionDuringRun as e:
                error = True
            except Exception as e:
                error = True
                if not batchmode:
                    raise e
                else:
                    traceback.print_exc()

            framework.includes = origIncludes
            sys.path = origSysPath

            with DBService.fromConfig(self.dbconfig) as service:
                if not error:
                    pass
                    service.doneWorkItem(item["id"])
                else:
                    numErrors += 1
                    service.errorWorkItem(item["id"])
                item = service.aquireWorkItem()

        if numErrors > 0:
            logging.warning("Encountered %i errors in configurations." % (numErrors))


if __name__ == '__main__':
    main()
