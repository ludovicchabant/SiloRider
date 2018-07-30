import logging
from ..parse import parse_mf2


logger = logging.getLogger(__name__)


def get_named_urls(config, names):
    named_urls = None
    if config.has_section('urls'):
        named_urls = config.items('urls')
    if not names:
        return [url for (_, url) in named_urls]

    return [url for (name, url) in named_urls
            if name in names]


def get_named_silos(silos, names):
    if not names:
        return silos

    valid_names = set([s.name for s in silos])
    for n in names:
        if n not in valid_names:
            raise Exception("No such silo: %s" % n)

    res = []
    for s in silos:
        if s.name in names:
            res.append(s)
    return res


def populate_cache(ctx):
    urls = get_named_urls(ctx.config, ctx.args.url)
    for url in urls:
        logger.info("Caching entries from %s" % url)
        _populate_cache_for_url(url, ctx)


def _populate_cache_for_url(url, ctx):
    import mf2util
    import dateutil.parser

    silos = get_named_silos(ctx.silos, ctx.args.silo)

    until_dt = None
    if ctx.args.until:
        until_dt = dateutil.parser.parse(ctx.args.until).date()
        logger.debug("Populating cache until: %s" % until_dt)

    mf_obj = parse_mf2(url)
    mf_dict = mf_obj.to_dict()
    for entry in mf_dict.get('items', []):
        entry_props = entry.get('properties')
        if not entry_props:
            logger.warning("Found entry without any properties.")
            continue

        entry_url = entry_props.get('url')
        if not entry_url:
            logger.warning("Found entry without any URL.")
            continue

        if isinstance(entry_url, list):
            entry_url = entry_url[0]

        if until_dt:
            entry_published = entry_props.get('published')
            if not entry_published:
                logger.warning("Entry '%s' has not published date." %
                               entry_url)
                continue

            if isinstance(entry_published, list):
                entry_published = entry_published[0]

            entry_published_dt = mf2util.parse_datetime(entry_published)
            if entry_published_dt and entry_published_dt.date() > until_dt:
                continue

        logger.debug("Adding entry to cache: %s" % entry_url)
        for silo in silos:
            ctx.cache.addPost(silo.name, entry_url)
