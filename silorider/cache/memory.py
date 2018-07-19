from .base import Cache


class MemoryCache(Cache):
    def __init__(self):
        self._vals = {}
        self._posted = {}

    def getCustomValue(self, name, valtype=str):
        return self._vals.get(name)

    def setCustomValue(self, name, val):
        self._vals[name] = val

    def wasPosted(self, silo_name, entry_uri):
        uris = self._posted.get(silo_name)
        if uris:
            return entry_uri in uris
        return False

    def addPost(self, silo_name, entry_uri):
        uris = self._posted.setdefault(silo_name, set())
        uris.add(entry_uri)
