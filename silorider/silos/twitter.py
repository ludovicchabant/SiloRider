import os.path
import logging
import tweepy
import urllib.parse
from .base import Silo, SiloProfileUrlHandler
from ..format import CardProps, UrlFlattener
from ..parse import strip_img_alt


logger = logging.getLogger(__name__)


class _CompositeClient:
    def __init__(self,
            consumer_key, consumer_secret,
            access_token_key, access_token_secret):
        self.v2 = tweepy.Client(
            None, # using OAuth v1
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token_key,
            access_token_secret=access_token_secret)

        auth_v1 = tweepy.OAuth1UserHandler(
                consumer_key, consumer_secret,
                access_token_key, access_token_secret)
        self.v1 = tweepy.API(auth_v1)

    def create_tweet(self, *args, **kwargs):
        return self.v2.create_tweet(*args, **kwargs)

    def simple_upload(self, *args, **kwargs):
        return self.v1.simple_upload(*args, **kwargs)


class TwitterSilo(Silo):
    SILO_TYPE = 'twitter'
    _CLIENT_CLASS = _CompositeClient

    def __init__(self, ctx):
        super().__init__(ctx)
        self.client = None

    def authenticate(self, ctx):
        force = ctx.exec_ctx.args.force

        # Get the app info tokens.
        client_token = self.getCacheItem('clienttoken')
        if not client_token or force:
            logger.info("Please enter consumer tokens (aka API tokens) for %s:" %
                        self.ctx.silo_name)
            consumer_key = input("Consumer Key: ")
            consumer_secret = input("Consumer Secret: ")
            client_token = '%s,%s' % (consumer_key, consumer_secret)
            self.setCacheItem('clienttoken', client_token)

        # Generate an access token by making the user login and authorize
        # our app.
        access_token = self.getCacheItem('accesstoken')
        if not access_token or force:
            self._ensureClient()
            auth_url = self.client.v1.auth.get_authorization_url()
            logger.info("Please authorize SiloRider with Twitter for %s at: %s" %
                        (self.ctx.silo_name, auth_url))
            logger.info("And then enter the OAuth verifier token here:")
            verifier_token = input("Verifier Token:")

            access_key, access_secret = self.client.v1.auth.get_access_token(
                verifier_token)
            access_token = '%s,%s' % (access_key, access_secret)
            self.setCacheItem('accesstoken', access_token)

    def onPostStart(self, ctx):
        if not ctx.args.dry_run:
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

    def getProfileUrlHandler(self):
        return TwitterProfileUrlHandler()

    def getEntryCard(self, entry, ctx):
        return self.formatEntry(
                entry,
                limit=280,
                card_props=CardProps('name', 'twitter'),
                profile_url_handlers=ctx.profile_url_handlers,
                url_flattener=TwitterUrlFlattener())

    def mediaCallback(self, tmpfile, mt, url, desc):
        url_parsed = urllib.parse.urlparse(url)
        fname = os.path.basename(url_parsed.path)
        with open(tmpfile, 'rb') as tmpfp:
            logger.debug("Uploading %s to twitter" % fname)
            media = self.client.simple_upload(fname, file=tmpfp)
        return media.media_id

    def postEntry(self, entry_card, media_ids, ctx):
        self.client.create_tweet(text=entry_card.text, media_ids=media_ids)


TWITTER_NETLOCS = ['twitter.com', 'www.twitter.com']


class TwitterProfileUrlHandler(SiloProfileUrlHandler):
    def handleUrl(self, text, raw_url):
        url = urllib.parse.urlparse(raw_url)

        # Is it a Twitter URL?
        if url.netloc not in TWITTER_NETLOCS:
            return None

        path = url.path.lstrip('/')
        # Is it a profile URL?
        if '/' not in path:
            return '@' + path

        return None


class TwitterUrlFlattener(UrlFlattener):
    def replaceHref(self, text, raw_url, ctx):
        url = urllib.parse.urlparse(raw_url)

        # Is it a Twitter URL?
        if url.netloc not in TWITTER_NETLOCS:
            return None

        path = url.path.lstrip('/')
        # Is it a profile URL?
        if '/' not in path:
            return '@' + path

        return None

    def measureUrl(self, raw_url):
        return 23
