import re
import os.path
import json
import time
import urllib.parse
import getpass
import logging
import datetime
from .base import Silo
from ..format import CardProps, UrlFlattener, URLMODE_ERASE

import atproto
from atproto import models as atprotomodels


logger = logging.getLogger(__name__)


class _BlueskyClient(atproto.Client):
    def __init__(self, *args, **kwargs):
        atproto.Client.__init__(self, *args, **kwargs)

    def send_post(self, text, *, post_datetime=None, embed=None, facets=None):
        # Override the atproto.Client send_post function because it
        # doesn't support facets yet. The code is otherwise more or
        # less identical.
        repo = self.me.did
        langs = [atprotomodels.languages.DEFAULT_LANGUAGE_CODE1]

        # Make sure we have a proper time zone.
        post_datetime = post_datetime or datetime.datetime.now()
        if not post_datetime.tzinfo:
            tz_dt = datetime.datetime.now().astimezone()
            post_datetime = post_datetime.replace(tzinfo=tz_dt.tzinfo)
        created_at = post_datetime.isoformat()

        # Do it!
        data = atprotomodels.ComAtprotoRepoCreateRecord.Data(
                repo=repo,
                collection=atprotomodels.ids.AppBskyFeedPost,
                record=atprotomodels.AppBskyFeedPost.Main(
                    createdAt=created_at,
                    text=text,
                    facets=facets,
                    embed=embed,
                    langs=langs)
                )
        self.com.atproto.repo.create_record(data)


class BlueskySilo(Silo):
    SILO_TYPE = 'bluesky'
    PHOTO_LIMIT = 976560
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
            self.setCacheItem('email', email)

            password = getpass.getpass(prompt="Application password: ")
            profile = self.client.login(email, password)

            logger.info("Authenticated as %s" % profile.display_name)
            self.setCacheItem('password', password)

    def onPostStart(self, ctx):
        if not ctx.args.dry_run:
            email = self.getCacheItem('email')
            password = self.getCacheItem('password')
            if not email or not password:
                raise Exception("Please authenticate Bluesky silo %s" %
                                self.ctx.silo_name)
            self.client.login(email, password)

    def getEntryCard(self, entry, ctx):
        # We use URLMODE_ERASE to remove all hyperlinks from the
        # formatted text, and we later add them as facets to the atproto
        # record.
        url_flattener = BlueskyUrlFlattener()
        card = self.formatEntry(
            entry,
            limit=300,
            # Use Twitter's meta properties
            card_props=CardProps('name', 'twitter'),
            profile_url_handlers=ctx.profile_url_handlers,
            url_flattener=url_flattener,
            url_mode=URLMODE_ERASE)
        card.__bsky_url_flattener = url_flattener
        return card

    def mediaCallback(self, tmpfile, mt, url, desc):
        with open(tmpfile, 'rb') as tmpfp:
            data = tmpfp.read()

        logger.debug("Uploading image to Bluesky (%d bytes) with description: %s" %
                     (len(data), desc))
        upload = self.client.com.atproto.repo.upload_blob(data)

        if desc is None:
            desc = ""
        return atprotomodels.AppBskyEmbedImages.Image(alt=desc, image=upload.blob)

    def postEntry(self, entry_card, media_ids, ctx):
        # Add images as an embed on the atproto record.
        embed = None
        if media_ids:
            embed = atprotomodels.AppBskyEmbedImages.Main(images=media_ids)

        # Grab any URLs detected by our URL flattener and add them as
        # facets on the atproto record.
        facets = None
        url_flattener = entry_card.__bsky_url_flattener
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
        entry_dt = entry_card.entry.get('published')
        self.client.send_post(
                text=entry_card.text, post_datetime=entry_dt, embed=embed,
                facets=facets)


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

        # Always keep the text as-is.
        return text

    def measureUrl(self, url):
        return len(url)

    def reset(self):
        self.urls = []

