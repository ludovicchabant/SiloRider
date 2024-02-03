import json
import logging
import requests
import pyfacebook
from datetime import datetime
from requests_oauthlib.oauth2_session import OAuth2Session
from requests_oauthlib.compliance_fixes.facebook import facebook_compliance_fix
from .base import Silo
from ..format import CardProps


logger = logging.getLogger(__name__)


class FacebookSilo(Silo):
    SILO_TYPE = 'facebook'
    PHOTO_LIMIT = 4000000
    _CLIENT_CLASS = pyfacebook.GraphAPI

    def __init__(self, ctx):
        super().__init__(ctx)

        self.client = None

    def authenticate(self, ctx):
        force = ctx.exec_ctx.args.force

        # Get the app info tokens.
        app_id = self.getCacheItem('appid')
        if not app_id or force:
            logger.info("Plase enter Facebook app ID for %s" %
                        self.ctx.silo_name)
            app_id = input("App ID:")
            self.setCacheItem('appid', app_id)

        app_secret = self.getCacheItem('appsecret')
        if not app_secret or force:
            logger.info("Please enter Facebook app secret for %s" %
                        self.ctx.silo_name)
            app_secret = input("App Secret:")
            self.setCacheItem('appsecret', app_secret)

        # Start the OAuth authorization flow.
        return_url = 'https://bolt80.com/silorider/auth_success.php'
        perms = ['pages_show_list', 'pages_manage_posts']

        auth_client = self._CLIENT_CLASS(
                app_id=app_id,
                app_secret=app_secret,
                oauth_flow=True)

        login_url, state = auth_client.get_authorization_url(return_url, perms)
        logger.info("Please authenticate at the following URL:")
        logger.info(login_url)
        resp_url = input("Paste the redirected URL here:")
        if not resp_url:
            logger.info("Authentication aborted!")
            return

        # Get the long-lived user access token.
        user_access_token = auth_client.exchange_user_access_token(
                response=resp_url,
                redirect_uri=return_url,
                scope=perms)
        logger.info("Got user access token, exchanging it for a long-lived one.")
        print(user_access_token)
        ll_user_access_token = auth_client.exchange_long_lived_user_access_token(
                user_access_token['access_token'])
        logger.info("Got long-lived user access token.")
        print(ll_user_access_token)

        # Get the user account information where we can find which page
        # we need to publish to.
        auth_client.access_token = ll_user_access_token['access_token']

        user = auth_client.get('/me', None)
        print(user)

        accounts = auth_client.get('/me/accounts', None)
        print(accounts)
        pages = accounts['data']
        if len(pages) > 1:
            logger.info("Choose which page to publish to:")
            for i, page in enumerate(pages):
                logger.info("%d: %s" % (i + 1, page['name']))
            page_idx = input("Enter page index:")
            page = pages[page_idx - 1]
        else:
            page = pages[0]

        # Get a long-lived page access token for the chosen page.
        logger.info("Requesting long-lived page access token for: %s" % page['name'])
        ll_page_access_token = auth_client.exchange_long_lived_page_access_token(
                user['id'], page['access_token'])
        logger.info("Got long-lived page access token")
        print(ll_page_access_token)

        id_to_find = page['id']
        page = next(
                filter(
                    lambda p: p['id'] == id_to_find,
                    ll_page_access_token['data']),
                None)
        if page is None:
            logger.error("Can't find selected page in authorization response!")
            return

        self.setCacheItem("accesstoken", page['access_token'])
        self.setCacheItem("objectid", page['id'])
        logger.info("Page access token saved.")

    def onPostStart(self, ctx):
        if not ctx.args.dry_run:
            self._ensureClient()

    def _ensureClient(self):
        if self.client is not None:
            return

        logger.debug("Creating Facebook GraphAPI client.")

        app_id = self.getCacheItem('appid')
        app_secret = self.getCacheItem('appsecret')
        access_token = self.getCacheItem('accesstoken')
        if not app_id or not access_token or not app_secret:
            raise Exception("Facebook silo '%s' isn't authenticated." %
                            self.name)

        self.page_id = self.getCacheItem("objectid")
        if not self.page_id:
            raise Exception("Facebook silo '%s' doesn't have a page ID." %
                            self.name)

        self.client = self._CLIENT_CLASS(
            app_id=app_id,
            app_secret=app_secret,
            access_token=access_token)

    def getEntryCard(self, entry, ctx):
        return self.formatEntry(
                entry,
                card_props=CardProps('property', 'og'),
                profile_url_handlers=ctx.profile_url_handlers)

    def mediaCallback(self, tmpfile, mt, url, desc):
        with open(tmpfile, 'rb') as fp:
            resp = self.client.post_object(
                object_id=self.page_id,
                connection='photos',
                files={tmpfile: fp},
                data={'caption': desc, 'published': False})
        logger.debug("Uploaded photo '%s' as object: %s" % (url, resp))
        return resp['id']

    def postEntry(self, entry_card, media_ids, ctx):
        data={'message': entry_card.text}
        if media_ids:
            attached_media = []
            for media_id in media_ids:
                attached_media.append({"media_fbid": media_id})
            # Very bad: it looks like pyfacebook doesn't deep-JSONify
            # things inside the data dictionary. So facebook returns
            # an error code if we don't JSONify this array ourselves.
            data['attached_media'] = json.dumps(attached_media)

        logger.debug("Posting Facebook update: %s" % entry_card.text)
        logger.debug("Using data: %s" % data)

        resp = self.client.post_object(
            object_id=self.page_id,
            connection='feed',
            data=data)
        logger.debug("Posted as object: %s" % resp)

