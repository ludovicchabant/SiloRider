import getpass
import logging
import mastodon
from .base import Silo, upload_silo_media


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

    def onPostStart(self):
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

    def postEntry(self, entry, ctx):
        toottxt = self.formatEntry(entry, limit=500)
        if not toottxt:
            raise Exception("Can't find any content to use for the toot!")

        visibility = self.getConfigItem('toot_visibility', fallback='public')

        media_ids = upload_silo_media(entry, 'photo', self._media_callback)

        logger.debug("Posting toot: %s" % toottxt)
        self.client.status_post(toottxt, media_ids=media_ids,
                                visibility=visibility)

    def _media_callback(self, tmpfile, mt):
        with open(tmpfile, 'rb') as tmpfp:
            return self.client.media_post(tmpfp, mt)
