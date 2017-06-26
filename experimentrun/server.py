import Pyro4
import os
import psutil
import socket

from multiprocessing import Process

from . import framework


@Pyro4.expose
class JobDispatcher():
    def run(workingDirectory, config):
        os.chdir(workingDirectory)
        return framework.bootstrap(config)


def start(core):
    process = psutil.Process()
    process.cpu_affinity([core])
    daemon = Pyro4.Daemon()
    ns = Pyro4.locateNS()
    uri = daemon.register(JobDispatcher)
    name = socket.gethostname() + str(core)
    ns.register(
        name + "-" + str(core) +
        ".jobdispatcher", uri, metadata=['jobdispatcher'])
    daemon.requestLoop()


def main():
    p1 = Process(target=start, args=(0,))
    p1.start()

    p2 = Process(target=start, args=(3,))
    p2.start()

    p1.join()
    p2.join()


if __name__ == "__main__":
    main()
