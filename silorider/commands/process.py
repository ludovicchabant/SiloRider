import logging
from .utils import get_named_silos
from ..silos.base import SiloPostingContext
from ..parse import parse_url


logger = logging.getLogger(__name__)


def process_url(url, ctx):
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
        for silo in self.silos:
            silo.onPostStart()

    def postProcess(self):
        for silo in self.silos:
            silo.onPostEnd()

    def processEntry(self, entry):
        if self.isEntryFiltered(entry):
            logger.debug("Entry is filtered out: %s" % entry.best_name)
            return

        entry_url = entry.get('url')
        if not entry_url:
            logger.warning("Found entry without a URL.")
            return

        postctx = SiloPostingContext(self.ctx)
        no_cache = self.ctx.args.no_cache
        logger.debug("Processing entry: %s" % entry.best_name)
        for silo in self.silos:
            if no_cache or not self.ctx.cache.wasPosted(silo.name, entry_url):
                if not self.ctx.args.dry_run:
                    silo.postEntry(entry, postctx)
                    self.ctx.cache.addPost(silo.name, entry_url)
                else:
                    logger.info("Would post entry on %s: %s" %
                                (silo.name, entry.best_name))
            else:
                logger.debug("Skipping already posted entry on %s: %s" %
                             (silo.name, entry.best_name))

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
