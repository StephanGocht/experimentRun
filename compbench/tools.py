class Tool(object):
    def __init__(self, priority=0):
        print("Registered new Tool: %s" % (self.__class__.__name__))
        self.priority = priority
        self.config = None

    def run(self):
        pass
