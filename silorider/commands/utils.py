import logging
from ..parse import parse_url


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
    import dateutil.parser

    urls = get_named_urls(ctx.config, ctx.args.url)

    until_dt = None
    if ctx.args.until:
        until_dt = dateutil.parser.parse(ctx.args.until).date()
        logger.debug("Populating cache until: %s" % until_dt)

    for url in urls:
        logger.info("Caching entries from %s" % url)
        _populate_cache_for_url(url, ctx, until_dt=until_dt)


def _populate_cache_for_url(url, ctx, until_dt=None):
    silos = get_named_silos(ctx.silos, ctx.args.silo)

    feed = parse_url(url)

    for entry in feed.entries:
        entry_url = entry.get('url')
        if not entry_url:
            logger.warning("Found entry without any URL: %s" % repr(entry._mf_entry))
            continue

        if isinstance(entry_url, list):
            entry_url = entry_url[0]

        if until_dt:
            entry_published = entry.get('published')
            if not entry_published:
                logger.warning("Entry '%s' has not published date." %
                               entry_url)
                continue

            if isinstance(entry_published, list):
                entry_published = entry_published[0]

            if entry_published and entry_published.date() > until_dt:
                continue

        for silo in silos:
            if ctx.cache.wasPosted(silo.name, entry_url):
                logger.debug("Entry is already in '%s' cache: %s" % (silo.name, entry_url))
                continue

            if not ctx.args.dry_run:
                logger.debug("Adding entry to '%s' cache: %s" % (silo.name, entry_url))
                ctx.cache.addPost(silo.name, entry_url)
            else:
                logger.debug("Would add entry to '%s' cache: %s" % (silo.name, entry_url))
