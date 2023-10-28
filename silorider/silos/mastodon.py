import time
import getpass
import logging
import urllib.parse
import mastodon
from .base import Silo, SiloProfileUrlHandler
from ..format import CardProps


logger = logging.getLogger(__name__)


class MastodonSilo(Silo):
    SILO_TYPE = 'mastodon'
    _CLIENT_CLASS = mastodon.Mastodon

    def __init__(self, ctx):
        super().__init__(ctx)

        self.base_url = self.getConfigItem('url')
        if not self.base_url:
            raise Exception("No Mastodon instance URL defined for: %s",
                            self.ctx.silo_name)

        self.client = None

    def authenticate(self, ctx):
        force = ctx.exec_ctx.args.force

        client_token = self.getCacheItem('clienttoken')
        if not client_token or force:
            logger.info("Authenticating client app with Mastodon for %s" %
                        self.ctx.silo_name)
            pair = self._CLIENT_CLASS.create_app(
                'SiloRider',
                scopes=['read', 'write'],
                api_base_url=self.base_url
            )
            client_token = '%s,%s' % pair
            self.setCacheItem('clienttoken', client_token)

        client_id, client_secret = client_token.split(',')

        access_token = self.getCacheItem('accesstoken')
        if not access_token or force:
            m = self._CLIENT_CLASS(
                client_id=client_id,
                client_secret=client_secret,
                api_base_url=self.base_url)

            if ctx.exec_ctx.args.console:
                logger.info("Authenticating user with Mastodon for %s" %
                            self.ctx.silo_name)
                logger.info("Only access tokens will be stored -- your "
                            "username and password will be forgotten in "
                            "a second.")

                username = input("Username: ")
                if not username:
                    raise Exception("You must enter a username.")

                password = getpass.getpass(prompt="Password: ")

                try:
                    access_token = m.log_in(
                        username, password,
                        scopes=['read', 'write'])
                except mastodon.MastodonIllegalArgumentError as err:
                    raise Exception("Incorrect credientials") from err
                except mastodon.MastodonAPIError as err:
                    raise Exception("Autentication error") from err

                username = password = None

            else:
                logger.info("Once you've authorized silorider to access"
                            "your Mastodon account, paste the authentication "
                            "code back here:")

                import webbrowser
                req_url = m.auth_request_url(scopes=['write'])
                webbrowser.open(req_url)

                access_token = input("Authentication code: ")

            self.setCacheItem('accesstoken', access_token)

    def onPostStart(self, ctx):
        if not ctx.args.dry_run:
            self._ensureApp()

    def _ensureApp(self):
        if self.client is not None:
            return

        logger.debug("Creating Mastodon app.")
        client_token = self.getCacheItem('clienttoken')
        if not client_token:
            raise Exception("Mastodon silo '%s' isn't authenticated." %
                            self.name)

        client_id, client_secret = client_token.split(',')

        access_token = self.getCacheItem('accesstoken')
        if not access_token:
            raise Exception("Mastodon silo '%s' isn't authenticated." %
                            self.name)

        self.client = self._CLIENT_CLASS(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            api_base_url=self.base_url)

    def getProfileUrlHandler(self):
        return MastodonProfileUrlHandler()

    def getEntryCard(self, entry, ctx):
        return self.formatEntry(
                entry, limit=500,
                # Use Twitter's meta properties
                card_props=CardProps('name', 'twitter'))

    def mediaCallback(self, tmpfile, mt, url, desc):
        with open(tmpfile, 'rb') as tmpfp:
            logger.debug("Uploading to mastodon with description: %s" % desc)
            return self.client.media_post(
                    tmpfp, mime_type=mt, description=desc)

    def postEntry(self, entry_card, media_ids, ctx):
        visibility = self.getConfigItem('toot_visibility', fallback='public')

        tries_left = 5
        logger.debug("Posting toot: %s" % entry_card.text)
        while tries_left > 0:
            try:
                self.client.status_post(entry_card.text, media_ids=media_ids,
                                        visibility=visibility)
                break # if we got here without an exception, it's all good!
            except mastodon.MastodonAPIError as merr:
                if merr.args[1] == 422 and media_ids:
                    # Unprocessable entity error. This happens if we have
                    # uploaded some big images and the server is still
                    # processing them.  In this case, let's wait a second and
                    # try again.
                    logger.debug(
                        "Server may still be processing media... waiting"
                        "to retry")
                    time.sleep(1)
                    tries_left -= 1
                    continue
                raise

class MastodonProfileUrlHandler(SiloProfileUrlHandler):
    def handleUrl(self, text, raw_url):
        url = urllib.parse.urlparse(raw_url)
        server_url = url.netloc
        path = url.path.lstrip('/')
        if path.startswith('@') and '/' not in path:
            return '@%s%s' % (path, server_url)
        return None

