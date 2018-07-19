import os.path
import urllib.parse
import logging


logger = logging.getLogger(__name__)


class Cache:
    def getCustomValue(self, name, valtype=str):
        raise NotImplementedError()

    def setCustomValue(self, name, val):
        raise NotImplementedError()

    def wasPosted(self, silo_name, entry_uri):
        raise NotImplementedError()

    def addPost(self, silo_name, entry_uri):
        raise NotImplementedError()


class NullCache(Cache):
    def __init__(self):
        self._vals = {}

    def getCustomValue(self, name, valtype=str):
        return self._vals.get(name)

    def setCustomValue(self, name, val):
        self._vals[name] = val

    def wasPosted(self, silo_name, entry_uri):
        return False

    def addPost(self, silo_name, entry_uri):
        pass


def load_cache(config, cfg_dir):
    if not config.has_section('cache'):
        logger.warning("No cache configured!")
        return NullCache()

    cache_uri = config.get('cache', 'uri', fallback=None)
    if not cache_uri:
        return NullCache()

    res = urllib.parse.urlparse(cache_uri)
    if res.scheme == 'sqlite':
        from .sqlite import SqliteCache
        dbpath = res.netloc + res.path
        if cfg_dir:
            dbpath = os.path.join(cfg_dir, dbpath)
        return SqliteCache(dbpath, config)
    elif res.scheme == 'memory':
        from .memory import MemoryCache
        return MemoryCache()

    raise Exception("Unknown cache URI: %s" % cache_uri)
