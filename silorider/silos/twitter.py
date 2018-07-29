import logging
import twitter
from .base import Silo, upload_silo_media


logger = logging.getLogger(__name__)


class TwitterSilo(Silo):
    SILO_TYPE = 'twitter'
    _CLIENT_CLASS = twitter.Api

    def __init__(self, ctx):
        super().__init__(ctx)
        self.client = None

    def authenticate(self, ctx):
        force = ctx.exec_ctx.args.force

        client_token = self.getCacheItem('clienttoken')
        if not client_token or force:
            logger.info("Please enter Twitter consumer tokens for %s:" %
                        self.ctx.silo_name)
            consumer_key = input("Consumer Key: ")
            consumer_secret = input("Consumer Secret: ")
            client_token = '%s,%s' % (consumer_key, consumer_secret)
            self.setCacheItem('clienttoken', client_token)

        access_token = self.getCacheItem('accesstoken')
        if not access_token or force:
            logger.info("Please enter Twitter access tokens for %s:" %
                        self.ctx.silo_name)

            access_key = input("Access Token: ")
            access_secret = input("Access Token Secret: ")

            access_token = '%s,%s' % (access_key, access_secret)
            self.setCacheItem('accesstoken', access_token)

    def onPostStart(self):
        self._ensureClient()

    def _ensureClient(self):
        if self.client is not None:
            return

        logger.debug("Creating Twitter API client.")
        client_token = self.getCacheItem('clienttoken')
        if not client_token:
            raise Exception("Twitter silo '%s' isn't authenticated." %
                            self.name)

        client_key, client_secret = client_token.split(',')

        access_token = self.getCacheItem('accesstoken')
        if not access_token:
            raise Exception("Twitter silo '%s' isn't authenticated." %
                            self.name)

        access_key, access_secret = access_token.split(',')

        self.client = self._CLIENT_CLASS(
            consumer_key=client_key,
            consumer_secret=client_secret,
            access_token_key=access_key,
            access_token_secret=access_secret)

    def postEntry(self, entry, ctx):
        tweettxt = self.formatEntry(entry, limit=280)
        if not tweettxt:
            raise Exception("Can't find any content to use for the tweet!")

        logger.debug("Posting tweet: %s" % tweettxt)
        media_urls = entry.get('photo', [], force_list=True)
        self.client.PostUpdate(tweettxt, media=media_urls)
