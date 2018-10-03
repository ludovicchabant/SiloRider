import logging
import ronkyuu
from .base import Silo
from ..config import has_lxml


logger = logging.getLogger(__name__)


class WebmentionSilo(Silo):
    SILO_TYPE = 'webmention'

    def __init__(self, ctx):
        super().__init__(ctx)
        self.client = None
        ronkyuu.setParser('lxml' if has_lxml else 'html5lib')

    def authenticate(self, ctx):
        logger.info("Webmention silo doesn't require authentication.")

    def postEntry(self, entry, ctx):
        source_url = entry.url
        logger.debug("Finding mentions in: %s" % source_url)
        refs = ronkyuu.findMentions(source_url)
        for r in refs.get('refs', []):
            logger.debug("Sending webmention: %s -> %s" % (source_url, r))
            ronkyuu.sendWebmention(source_url, r)
