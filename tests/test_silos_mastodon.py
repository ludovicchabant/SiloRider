import pytest
from .mockutil import mock_urllib


def test_one_article(cli, feedutil, mastmock):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<h1 class="p-name">A new article</h1>
<div class="e-content">
<p>This is the text of the article.</p>
<p>It has 2 paragraphs.</p>
</div>
<a class="u-url" href="https://example.org/a-new-article">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'mastodon', url='/blah')
    mastmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process', feed)
    assert ctx.cache.wasPosted('test', 'https://example.org/a-new-article')
    toot = ctx.silos[0].client.toots[0]
    assert toot == ('A new article https://example.org/a-new-article',
                    None, 'public')


def test_one_micropost(cli, feedutil, mastmock):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a quick update.</p>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'mastodon', url='/blah')
    mastmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process', feed)
    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.toots[0]
    assert toot == ("This is a quick update.", None, 'public')


def test_one_micropost_with_one_photo(cli, feedutil, mastmock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a quick photo update.</p>
<div>
    <a class="u-photo" href="/fullimg.jpg"><img src="/thumbimg.jpg"/></a>
</div>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'mastodon', url='/blah')
    mastmock.installTokens(cli, 'test')

    with monkeypatch.context() as m:
        import silorider.silos.mastodon
        mock_urllib(m)
        m.setattr(silorider.silos.mastodon.MastodonSilo, '_media_callback',
                  _patched_media_callback)
        ctx, _ = cli.run('process', feed)

    assert ctx.cache.wasPosted('test', '/01234.html')
    media = ctx.silos[0].client.media[0]
    assert media == ('/retrieved/fullimg.jpg', 'image/jpeg', 1)
    toot = ctx.silos[0].client.toots[0]
    assert toot == ("This is a quick photo update.", [1], 'public')


def test_one_micropost_with_two_photos(cli, feedutil, mastmock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a photo update with 2 photos.</p>
<div>
    <a class="u-photo" href="/fullimg1.jpg"><img src="/thumbimg1.jpg"/></a>
    <a class="u-photo" href="/fullimg2.jpg"><img src="/thumbimg2.jpg"/></a>
</div>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'mastodon', url='/blah')
    mastmock.installTokens(cli, 'test')

    with monkeypatch.context() as m:
        import silorider.silos.mastodon
        mock_urllib(m)
        m.setattr(silorider.silos.mastodon.MastodonSilo, '_media_callback',
                  _patched_media_callback)
        ctx, _ = cli.run('process', feed)

    assert ctx.cache.wasPosted('test', '/01234.html')
    media = ctx.silos[0].client.media[0]
    assert media == ('/retrieved/fullimg1.jpg', 'image/jpeg', 1)
    media = ctx.silos[0].client.media[1]
    assert media == ('/retrieved/fullimg2.jpg', 'image/jpeg', 2)
    toot = ctx.silos[0].client.toots[0]
    assert toot == ("This is a photo update with 2 photos.", [1, 2], 'public')


def _patched_media_callback(self, tmpfile, mt):
    return self.client.media_post(tmpfile, mt)


@pytest.fixture(scope='session')
def mastmock():
    from silorider.silos.mastodon import MastodonSilo
    MastodonSilo._CLIENT_CLASS = MastodonMock
    return MastodonMockUtil()


class MastodonMock:
    @staticmethod
    def create_app(app_name, scopes, api_base_url):
        return ('TEST_CLIENT_ID', 'TEST_CLIENT_SECRET')

    def __init__(self, client_id, client_secret, access_token, api_base_url):
        self.toots = []
        self.media = []
        self.next_mid = 1

    def log_in(self, username, password, scopes):
        return 'TEST_ACCESS_TOKEN'

    def auth_request_url(self, scopes):
        return 'https://example.org/auth'

    def status_post(self, toot, media_ids=None, visibility=None):
        self.toots.append((toot, media_ids, visibility))

    def media_post(self, filename, mimetype):
        mid = self.next_mid
        self.next_mid += 1
        self.media.append((filename, mimetype, mid))
        return mid


class MastodonMockUtil:
    def installTokens(self, cli, silo_name):
        def do_install_tokens(ctx):
            ctx.cache.setCustomValue(
                '%s_clienttoken' % silo_name,
                'TEST_CLIENT_ID,TEST_CLIENT_SECRET')
            ctx.cache.setCustomValue(
                '%s_accesstoken' % silo_name,
                'TEST_ACCESS_TOKEN')

        cli.preExecHook(do_install_tokens)
