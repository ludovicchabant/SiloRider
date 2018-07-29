import pytest


def test_one_article(cli, feedutil, tweetmock):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<h1 class="p-name">A new article</h1>
<div class="e-content">
<p>This is the text of the article.</p>
<p>It has 2 paragraphs.</p>
</div>
<a class="u-url" href="https://example.org/a-new-article">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process', feed)
    assert ctx.cache.wasPosted('test', 'https://example.org/a-new-article')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ('A new article https://example.org/a-new-article', [])


def test_one_micropost(cli, feedutil, tweetmock):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a quick update.</p>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process', feed)
    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("This is a quick update.", [])


def test_one_micropost_with_one_photo(cli, feedutil, tweetmock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a quick photo update.</p>
<div>
    <a class="u-photo" href="/fullimg.jpg"><img src="/thumbimg.jpg"/></a>
</div>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process', feed)

    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("This is a quick photo update.", ['/fullimg.jpg'])


def test_one_micropost_with_two_photos(cli, feedutil, tweetmock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a photo update with 2 photos.</p>
<div>
    <a class="u-photo" href="/fullimg1.jpg"><img src="/thumbimg1.jpg"/></a>
    <a class="u-photo" href="/fullimg2.jpg"><img src="/thumbimg2.jpg"/></a>
</div>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process', feed)

    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("This is a photo update with 2 photos.",
                    ['/fullimg1.jpg', '/fullimg2.jpg'])


@pytest.fixture(scope='session')
def tweetmock():
    from silorider.silos.twitter import TwitterSilo
    TwitterSilo._CLIENT_CLASS = TwitterMock
    return TwitterMockUtil()


class TwitterMock:
    def __init__(self, consumer_key, consumer_secret,
                 access_token_key, access_token_secret):
        assert consumer_key == 'TEST_CLIENT_KEY'
        assert consumer_secret == 'TEST_CLIENT_SECRET'
        assert access_token_key == 'TEST_ACCESS_KEY'
        assert access_token_secret == 'TEST_ACCESS_SECRET'

        self.tweets = []

    def PostUpdate(self, tweet, media=None):
        self.tweets.append((tweet, media))


class TwitterMockUtil:
    def installTokens(self, cli, silo_name):
        def do_install_tokens(ctx):
            ctx.cache.setCustomValue(
                '%s_clienttoken' % silo_name,
                'TEST_CLIENT_KEY,TEST_CLIENT_SECRET')
            ctx.cache.setCustomValue(
                '%s_accesstoken' % silo_name,
                'TEST_ACCESS_KEY,TEST_ACCESS_SECRET')

        cli.preExecHook(do_install_tokens)
