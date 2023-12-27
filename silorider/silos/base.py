import os
import os.path
import uuid
import urllib.request
import logging
import tempfile
import mimetypes
from PIL import Image
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
    def dry_run(self):
        return self.exec_ctx.args.dry_run

    @property
    def config(self):
        return self.exec_ctx.config

    @property
    def cache(self):
        return self.exec_ctx.cache


class SiloAuthenticationContext(SiloContextBase):
    pass


class SiloPostingContext(SiloContextBase):
    def __init__(self, exec_ctx, profile_url_handlers=None):
        SiloContextBase.__init__(self, exec_ctx)
        self.profile_url_handlers = profile_url_handlers


class SiloProfileUrlHandler:
    def handleUrl(self, text, url):
        return None


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
        return format_entry(
                entry,
                silo_name=self.name, silo_type=self.SILO_TYPE,
                *args, **kwargs)

    def authenticate(self, ctx):
        raise NotImplementedError()

    def onPostStart(self, ctx):
        pass

    def getProfileUrlHandler(self):
        return None

    def getEntryCard(self, entry, ctx):
        raise NotImplementedError()

    def mediaCallback(self, tmpfile, mimetype, url, desc):
        raise NotImplementedError()

    def postEntry(self, entry_card, media_ids, ctx):
        raise NotImplementedError()

    def dryRunMediaCallback(self, tmpfile, mimetype, url, desc):
        logger.info("Would upload photo: %s (%s)" % (url, desc))
        return (url, desc)

    def dryRunPostEntry(self, entry_card, media_ids, ctx):
        logger.info(entry_card.text)
        if media_ids:
            logger.info("...with photos: %s" % media_ids)

    def onPostEnd(self, ctx):
        pass


def _get_silo_section_names(config):
    return [sn for sn in config.sections() if sn.startswith('silo:')]


def has_any_silo(config):
    return bool(_get_silo_section_names(config))


def load_silos(config, cache):
    from .print import PrintSilo
    from .bluesky import BlueskySilo
    from .facebook import FacebookSilo
    from .mastodon import MastodonSilo
    from .twitter import TwitterSilo
    from .webmention import WebmentionSilo
    silo_types = [
        PrintSilo,
        BlueskySilo,
        FacebookSilo,
        MastodonSilo,
        TwitterSilo,
        WebmentionSilo]
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


def upload_silo_media(card, propname, callback, max_size=None):
    # The provided callback must take the parameters:
    #  tmpfile path, mimetype, original media url, media description
    with tempfile.TemporaryDirectory(prefix='SiloRider') as tmpdir:

        # Upload and use forced image, if any.
        if card.image:
            mid = _do_upload_silo_media(tmpdir, card.image, None, callback, max_size)
            if mid is not None:
                return [mid]

        # Look for media in the body of the original post.
        media_ids = None
        media_entries = card.entry.get(propname, [], force_list=True)
        if media_entries:
            media_ids = []
            for media_entry in media_entries:
                url, desc = _img_url_and_alt(media_entry)
                mid = _do_upload_silo_media(tmpdir, url, desc, callback, max_size)
                if mid is not None:
                    media_ids.append(mid)

    return media_ids


def _do_upload_silo_media(tmpdir, url, desc, callback, max_size=None):
    logger.debug("Downloading %s for upload to silo..." % url)
    mt, enc = mimetypes.guess_type(url, strict=False)
    if not mt:
        logger.debug("Can't guess MIME type, defaulting to jpg")
        mt = mimetypes.common_types['.jpg']

    ext = mimetypes.guess_extension(mt) or '.jpg'
    logger.debug("Got MIME type and extension: %s %s" % (mt, ext))

    try:
        tmpfile = os.path.join(tmpdir, str(uuid.uuid4()) + ext)
        logger.debug("Downloading photo to temporary file: %s" % tmpfile)
        tmpfile, headers = urllib.request.urlretrieve(url, filename=tmpfile)
        tmpfile = _ensure_file_not_too_large(tmpfile, max_size)
        return callback(tmpfile, mt, url, desc)
    finally:
        logger.debug("Cleaning up.")
        urllib.request.urlcleanup()


def _ensure_file_not_too_large(path, max_size):
    if max_size is None:
        return path

    file_size = os.path.getsize(path)
    if file_size <= max_size:
        return path

    loops = 0
    scale = 0.75
    path_no_ext, ext = os.path.splitext(path)
    smaller_path = '%s_bsky%s' % (path_no_ext, ext)
    with Image.open(path) as orig_im:
        # Resize down 75% until we get below the size limit.
        img_width, img_height = orig_im.size
        while loops < 10:
            logger.debug("Resizing '%s' by a factor of %f" % (path, scale))
            img_width = int(img_width * scale)
            img_height = int(img_height * scale)
            with orig_im.resize((img_width, img_height)) as smaller_im:
                smaller_im.save(smaller_path)

            file_size = os.path.getsize(smaller_path)
            logger.debug("Now got file size %d (max size %d)" % (file_size, max_size))
            if file_size <= max_size:
                return smaller_path

            scale = scale * scale
            loops += 1

    raise Exception("Can't reach a small enough image to upload!")


def _img_url_and_alt(media_entry):
    # If an image has an alt attribute, the entry comes as a dictionary
    # with 'value' for the url and 'alt' for the description.
    if isinstance(media_entry, str):
        return media_entry, None
    if isinstance(media_entry, dict):
        logger.debug("Got alt text for image! %s" % media_entry['alt'])
        return media_entry['value'], media_entry['alt']
    raise Exception("Unexpected media entry: %s" % media_entry)
