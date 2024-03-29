import os.path
import pytest
from .mockutil import mock_urllib


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
    cli.setFeedConfig('feed', feed)
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process')
    assert ctx.cache.wasPosted('test', 'https://example.org/a-new-article')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ('A new article https://example.org/a-new-article', [])


def test_one_micropost(cli, feedutil, tweetmock):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a quick update.</p>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    cli.setFeedConfig('feed', feed)
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process')
    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("This is a quick update.", [])


def test_one_micropost_with_mention(cli, feedutil, tweetmock):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">Hey <a href="https://twitter.com/jack">Jacky</a>
you should fix your stuff!</p>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    cli.setFeedConfig('feed', feed)
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process')
    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("Hey @jack\nyou should fix your stuff!", [])


def test_one_micropost_with_one_photo(cli, feedutil, tweetmock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a quick photo update.</p>
<div>
    <a class="u-photo" href="/fullimg.jpg"><img src="/thumbimg.jpg"/></a>
</div>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    cli.setFeedConfig('feed', feed)
    tweetmock.installTokens(cli, 'test')

    with monkeypatch.context() as m:
        import silorider.silos.twitter
        mock_urllib(m)
        m.setattr(os.path, 'getsize', lambda path: 42)
        m.setattr(silorider.silos.twitter.TwitterSilo, 'mediaCallback',
                  _patched_media_callback)
        ctx, _ = cli.run('process')

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
    cli.setFeedConfig('feed', feed)
    tweetmock.installTokens(cli, 'test')

    with monkeypatch.context() as m:
        import silorider.silos.twitter
        mock_urllib(m)
        m.setattr(os.path, 'getsize', lambda path: 42)
        m.setattr(silorider.silos.twitter.TwitterSilo, 'mediaCallback',
                  _patched_media_callback)
        ctx, _ = cli.run('process')

    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("This is a photo update with 2 photos.",
                    ['/fullimg1.jpg', '/fullimg2.jpg'])


def test_micropost_with_long_text_and_link(cli, feedutil, tweetmock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<div class="p-name">
    <p>This a pretty long text that has a link in it :) We want to make sure it gets to the limit of what Twitter allows, so that we can test there won't be any off-by-one errors in measurements. Here is a <a href="https://docs.python.org/3/library/textwrap.html">link to Python's textwrap module</a>, which is appropriate!!!</p>
    </div>
    <a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    cli.setFeedConfig('feed', feed)
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process')
    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("This a pretty long text that has a link in it :) We want to make sure it gets to the limit of what Twitter allows, so that we can test there won't be any off-by-one errors in measurements. Here is a link to Python's textwrap module, which is appropriate!!! https://docs.python.org/3/library/textwrap.html",
            [])


def test_micropost_with_too_long_text_and_link_1(cli, feedutil, tweetmock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<div class="p-name">
    <p>This time we have a text that's slightly too long, with <a href="https://thisdoesntmatter.com">a link here</a>. We'll be one character too long, with a short word at the end to test the shortening algorithm. Otherwise, don't worry about it. Blah blah blah. Trying to get to the limit. Almost here yes</p>
    </div>
    <a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    cli.setFeedConfig('feed', feed)
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process')
    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("This time we have a text that's slightly too long, with a link here. We'll be one character too long, with a short word at the end to test the shortening algorithm. Otherwise, don't worry about it. Blah blah blah. Trying to get to the limit. Almost here... /01234.html",
            [])


def test_micropost_with_too_long_text_and_link_2(cli, feedutil, tweetmock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<div class="p-name">
    <p>This time we have a text that's slightly too long, with <a href="https://thisdoesntmatter.com">a link here</a>. We'll be one character too long, with a loooooong word at the end to test the shortening algorithm. Otherwise, don't worry about it. Blah blah blah. Our long word is: califragilisticastuff</p>
    </div>
    <a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'twitter', url='/blah')
    cli.setFeedConfig('feed', feed)
    tweetmock.installTokens(cli, 'test')

    ctx, _ = cli.run('process')
    assert ctx.cache.wasPosted('test', '/01234.html')
    toot = ctx.silos[0].client.tweets[0]
    assert toot == ("This time we have a text that's slightly too long, with a link here. We'll be one character too long, with a loooooong word at the end to test the shortening algorithm. Otherwise, don't worry about it. Blah blah blah. Our long word is:... /01234.html",
            [])


def _patched_media_callback(self, tmpfile, mt, url, desc):
    return self.client.simple_upload(url)


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
        self.media = []

    def create_tweet(self, text, media_ids=None):
        media_names = []
        if media_ids:
            for mid in media_ids:
                assert(self.media[mid] is not None)
                media_names.append(self.media[mid])
                self.media[mid] = None
        assert all([m is None for m in self.media])

        self.tweets.append((text, media_names))
        self.media = []

    def simple_upload(self, fname, file=None):
        self.media.append(fname)
        return len(self.media) - 1


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
