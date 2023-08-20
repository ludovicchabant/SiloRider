import re
import json
import time
import urllib.parse
import getpass
import logging
import datetime
from .base import Silo, upload_silo_media
from ..format import UrlFlattener, URLMODE_ERASE

import atproto
import atproto.xrpc_client.models as atprotomodels


logger = logging.getLogger(__name__)


class _BlueskyClient(atproto.Client):
    def __init__(self, *args, **kwargs):
        atproto.Client.__init__(self, *args, **kwargs)

    def send_post(self, text, embed=None, facets=None):
        # Override the atproto.Client send_post function because it
        # doesn't support facets yet. The code is otherwise more or
        # less identical.
        repo = self.me.did
        langs = [atprotomodels.languages.DEFAULT_LANGUAGE_CODE1]
        data = atprotomodels.ComAtprotoRepoCreateRecord.Data(
                repo=repo,
                collection=atprotomodels.ids.AppBskyFeedPost,
                record=atprotomodels.AppBskyFeedPost.Main(
                    createdAt=datetime.datetime.now().isoformat(),
                    text=text,
                    facets=facets,
                    embed=embed,
                    langs=langs)
                )
        self.com.atproto.repo.create_record(data)


class BlueskySilo(Silo):
    SILO_TYPE = 'bluesky'
    _DEFAULT_SERVER = 'bsky.app'
    _CLIENT_CLASS = _BlueskyClient

    def __init__(self, ctx):
        super().__init__(ctx)

        base_url = self.getConfigItem('url')
        self.client = self._CLIENT_CLASS(base_url)

    def authenticate(self, ctx):
        force = ctx.exec_ctx.args.force

        password = self.getCacheItem('password')
        if not password or force:
            logger.info("Authenticating client app with Bluesky for %s" %
                        self.ctx.silo_name)
            email = input("Email: ")
            password = getpass.getpass(prompt="Application password: ")
            profile = self.client.login(email, password)

            logger.info("Authenticated as %s" % profile.displayName)
            self.setCacheItem('email', email)
            self.setCacheItem('password', password)

    def onPostStart(self, ctx):
        if not ctx.args.dry_run:
            email = self.getCacheItem('email')
            password = self.getCacheItem('password')
            if not email or not password:
                raise Exception("Please authenticate Bluesky silo %s" %
                                self.ctx.silo_name)
            self.client.login(email, password)

    def postEntry(self, entry, ctx):
        # We use URLMODE_ERASE to remove all hyperlinks from the
        # formatted text, and we later add them as facets to the atproto
        # record.
        url_flattener = BlueskyUrlFlattener()
        posttxt = self.formatEntry(
            entry,
            limit=256,
            url_flattener=url_flattener,
            url_mode=URLMODE_ERASE)
        if not posttxt:
            raise Exception("Can't find any content to use for the post!")

        # Upload the images as blobs and add them as an embed on the
        # atproto record.
        images = upload_silo_media(entry, 'photo', self._media_callback)

        embed = None
        if images:
            embed = atprotomodels.AppBskyEmbedImages.Main(images=images)

        # Grab any URLs detected by our URL flattener and add them as
        # facets on the atproto record.
        facets = None
        if url_flattener.urls:
            facets = []
            for url_info in url_flattener.urls:
                # atproto requires an http or https scheme.
                start, end, url = url_info
                if not url.startswith('http'):
                    url = 'https://' + url

                facet = atprotomodels.AppBskyRichtextFacet.Main(
                    features=[atprotomodels.AppBskyRichtextFacet.Link(uri=url)],
                    index=atprotomodels.AppBskyRichtextFacet.ByteSlice(
                        byteStart=start, byteEnd=end),
                    )
                facets.append(facet)

        # Create the record!
        self.client.send_post(text=posttxt, embed=embed, facets=facets)

    def dryRunPostEntry(self, entry, ctx):
        posttxt = self.formatEntry(entry, limit=256)
        logger.info("Post would be:")
        logger.info(posttxt)
        media_urls = entry.get('photo', [], force_list=True)
        if media_urls:
            logger.info("...with photos: %s" % str(media_urls))

    def _media_callback(self, tmpfile, mt, url, desc):
        with open(tmpfile, 'rb') as tmpfp:
            data = tmpfp.read()

        logger.debug("Uploading image to Bluesky (%d bytes) with description: %s" %
                     (len(data), desc))
        upload = self.client.com.atproto.repo.upload_blob(data)

        if desc is None:
            desc = ""
        return atprotomodels.AppBskyEmbedImages.Image(alt=desc, image=upload.blob)


BLUESKY_NETLOC = 'bsky.app'

# Match both links to a profile by name, and by ID
profile_path_re = re.compile(r'/profile/([\w\d\.]+|(did\:plc\:[\w\d]+))')


class BlueskyUrlFlattener(UrlFlattener):
    def __init__(self):
        self.urls = []

    def replaceHref(self, text, raw_url, ctx):
        url = urllib.parse.urlparse(raw_url)

        # If this is a Bluesky profile URL, replace it with a mention.
        if url.netloc == BLUESKY_NETLOC:
            m = profile_path_re.match(url.path)
            if m:
                return '@' + m.group(1)

        # Otherwise, keep track of where the URL is so we can add a facet
        # for it.
        start = ctx.byte_length
        end = start + len(text.encode())
        self.urls.append((start, end, raw_url))
        print("Gathered link: ", start, end, raw_url)

        # Always keep the text as-is.
        return text

    def measureUrl(self, url):
        return len(url)
