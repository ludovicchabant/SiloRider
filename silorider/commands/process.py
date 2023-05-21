import logging
import dateparser
from .utils import get_named_silos, get_named_urls
from ..silos.base import SiloPostingContext
from ..parse import parse_url


logger = logging.getLogger(__name__)


def process_urls(ctx):
    for url in get_named_urls(ctx.config, ctx.args.url):
        logger.info("Processing %s" % url)
        p = Processor(ctx, url)
        p.process()


class Processor:
    def __init__(self, ctx, url):
        self.ctx = ctx
        self.url = url
        self._silos = get_named_silos(ctx.silos, ctx.args.silo)

    @property
    def config(self):
        return self.ctx.config

    @property
    def silos(self):
        return self._silos

    def process(self):
        self.preProcess()

        feed = parse_url(self.url)
        for entry in feed.entries:
            self.processEntry(entry)

        self.postProcess()

    def preProcess(self):
        # Pre-parse the "since" and "until" dates/times.
        if self.ctx.args.since:
            self.ctx.args.since = dateparser.parse(self.ctx.args.since)
        if self.ctx.args.until:
            self.ctx.args.until = dateparser.parse(self.ctx.args.until)

        for silo in self.silos:
            silo.onPostStart(self.ctx)

    def postProcess(self):
        for silo in self.silos:
            silo.onPostEnd(self.ctx)

    def processEntry(self, entry):
        entry_url = entry.get('url')
        if not entry_url:
            logger.warning("Found entry without a URL: %s" % repr(entry._mf_entry))
            return

        if self.isEntryFiltered(entry):
            logger.debug("Entry is filtered out: %s" % entry_url)
            return

        postctx = SiloPostingContext(self.ctx)
        no_cache = self.ctx.args.no_cache
        only_since = self.ctx.args.since
        only_until = self.ctx.args.until
        logger.debug("Processing entry: %s" % entry_url)
        for silo in self.silos:
            if only_since or only_until:
                entry_dt = entry.get('published')
                if not entry_dt:
                    logger.warning(
                        "Skipping entry with no published date/time "
                        "for %s: %s" % (silo.name, entry_url))
                    continue

                # Strip entry datetime's time-zone information if we
                # don't have a time-zone info from the command line.
                if ((only_since and not only_since.tzinfo) or
                    (only_until and not only_until.tzinfo)):
                    entry_dt = entry_dt.replace(tzinfo=None)

                if only_since and entry_dt < only_since:
                    logger.info(
                        "Skipping entry older than specified date/time "
                        "for %s: %s" % (silo.name, entry_url))
                    continue
                if only_until and entry_dt > only_until:
                    logger.info(
                        "Skipping entry newer than specified date/time "
                        "for %s: %s" % (silo.name, entry_url))
                    continue

            if not no_cache and self.ctx.cache.wasPosted(silo.name, entry_url):
                logger.debug("Skipping already posted entry on %s: %s" %
                             (silo.name, entry_url))
                continue

            if not self.ctx.args.dry_run:
                try:
                    did_post = silo.postEntry(entry, postctx)
                except Exception as ex:
                    did_post = False
                    logger.error("Error posting: %s" % entry_url)
                    logger.error(ex)
                    if self.ctx.args.verbose:
                        raise
                if did_post is True or did_post is None:
                    self.ctx.cache.addPost(silo.name, entry_url)
            else:
                logger.info("Would post entry on %s: %s" %
                            (silo.name, entry_url))
                silo.dryRunPostEntry(entry, postctx)

    def isEntryFiltered(self, entry):
        if not self.config.has_section('filter'):
            return False

        items = self.config.items('filter')

        for name, value in items:
            if name.startswith('include_'):
                propname = name[8:]
                propvalue = entry.get(propname)
                for inc_val in value.split(','):
                    if inc_val in propvalue:
                        break
                else:
                    return True

            elif name.startswith('exclude_'):
                propname = name[8:]
                propvalue = entry.get(propname)
                for excl_val in value.split(','):
                    if excl_val in propvalue:
                        return True

        return False
