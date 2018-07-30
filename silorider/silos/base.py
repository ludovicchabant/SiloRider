import urllib.request
import logging
import mimetypes
from ..format import format_entry


logger = logging.getLogger(__name__)


class SiloCreationContext:
    def __init__(self, config, cache, silo_name):
        self.config = config
        self.cache = cache
        self.silo_name = silo_name


class SiloContextBase:
    def __init__(self, exec_ctx):
        self.exec_ctx = exec_ctx

    @property
    def args(self):
        return self.exec_ctx.args

    @property
    def config(self):
        return self.exec_ctx.config

    @property
    def cache(self):
        return self.exec_ctx.cache


class SiloAuthenticationContext(SiloContextBase):
    pass


class SiloPostingContext(SiloContextBase):
    pass


class Silo:
    SILO_TYPE = 'unknown'

    def __init__(self, ctx):
        self.ctx = ctx
        self._silo_cfg = dict(ctx.config.items('silo:%s' % self.name))

    @property
    def name(self):
        return self.ctx.silo_name

    def getConfigItem(self, name, fallback=None):
        return self._silo_cfg.get(name, fallback)

    def getConfigItems(self):
        return self._silo_cfg.copy()

    def getCacheItem(self, name, valtype=str):
        full_name = '%s_%s' % (self.name, name)
        return self.ctx.cache.getCustomValue(full_name, valtype=valtype)

    def setCacheItem(self, name, val):
        full_name = '%s_%s' % (self.name, name)
        return self.ctx.cache.setCustomValue(full_name, val)

    def formatEntry(self, entry, *args, **kwargs):
        return format_entry(entry, *args, **kwargs)

    def authenticate(self, ctx):
        raise NotImplementedError()

    def onPostStart(self):
        pass

    def postEntry(self, entry, ctx):
        raise NotImplementedError()

    def onPostEnd(self):
        pass


def _get_silo_section_names(config):
    return [sn for sn in config.sections() if sn.startswith('silo:')]


def has_any_silo(config):
    return bool(_get_silo_section_names(config))


def load_silos(config, cache):
    from .print import PrintSilo
    from .mastodon import MastodonSilo
    from .twitter import TwitterSilo
    silo_types = [PrintSilo, MastodonSilo, TwitterSilo]
    silo_dict = dict([(s.SILO_TYPE, s) for s in silo_types])

    silos = []
    sec_names = _get_silo_section_names(config)
    for sec_name in sec_names:
        silo_name = sec_name[5:]
        sec_items = dict(config.items(sec_name))
        silo_type = sec_items.get('type')
        if not silo_type:
            raise Exception("No silo type specified for: %s" % silo_name)

        silo_class = silo_dict.get(silo_type)
        if not silo_class:
            raise Exception("Unknown silo type: %s" % silo_type)

        logger.debug("Creating silo '%s' for '%s'." % (silo_type, silo_name))
        cctx = SiloCreationContext(config, cache, silo_name)
        silo = silo_class(cctx)
        silos.append(silo)
    return silos


def upload_silo_media(entry, propname, callback):
    media_ids = None
    urls = entry.get(propname, [], force_list=True)
    if urls:
        media_ids = []
        for url in urls:
            mid = _do_upload_silo_media(url, callback)
            if mid is not None:
                media_ids.append(mid)
    return media_ids


def _do_upload_silo_media(url, callback):
    logger.debug("Downloading %s for upload to silo..." % url)
    mt, enc = mimetypes.guess_type(url)
    if not mt:
        mt = mimetypes.common_types['.jpg']

    ext = mimetypes.guess_extension(mt) or '.jpg'
    logger.debug("Got MIME type and extension: %s %s" % (mt, ext))

    try:
        tmpfile, headers = urllib.request.urlretrieve(url)
        logger.debug("Using temporary file: %s" % tmpfile)
        return callback(tmpfile, mt)
    finally:
        logger.debug("Cleaning up.")
        urllib.request.urlcleanup()
