import pytest
import atproto.xrpc_client.models as atprotomodels
from .mockutil import mock_urllib


def test_one_article(cli, feedutil, bskymock):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<h1 class="p-name">A new article</h1>
<div class="e-content">
<p>This is the text of the article.</p>
<p>It has 2 paragraphs.</p>
</div>
<a class="u-url" href="https://example.org/a-new-article">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'bluesky')
    cli.setFeedConfig('feed', feed)
    bskymock.installCredentials(cli, 'test')

    ctx, _ = cli.run('process')
    assert ctx.cache.wasPosted('test', 'https://example.org/a-new-article')
    post = ctx.silos[0].client.posts[0]
    assert post == ('A new article https://example.org/a-new-article',
                    None, None)


def test_one_micropost(cli, feedutil, bskymock):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a quick update.</p>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'bluesky')
    cli.setFeedConfig('feed', feed)
    bskymock.installCredentials(cli, 'test')

    ctx, _ = cli.run('process')
    assert ctx.cache.wasPosted('test', '/01234.html')
    post = ctx.silos[0].client.posts[0]
    assert post == ("This is a quick update.", None, None)


def test_one_micropost_with_one_photo(cli, feedutil, bskymock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a quick photo update.</p>
<div>
    <a class="u-photo" href="/fullimg.jpg"><img src="/thumbimg.jpg"/></a>
</div>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'bluesky')
    cli.setFeedConfig('feed', feed)
    bskymock.installCredentials(cli, 'test')

    with monkeypatch.context() as m:
        import silorider.silos.bluesky
        mock_urllib(m)
        m.setattr(silorider.silos.bluesky.BlueskySilo, 'mediaCallback',
                  _patched_media_callback)
        ctx, _ = cli.run('process')

    assert ctx.cache.wasPosted('test', '/01234.html')
    blob = ctx.silos[0].client.blobs[0]
    assert blob == ('/retrieved/fullimg.jpg', None)
    post = ctx.silos[0].client.posts[0]
    assert post[1].images[0].__test_index == 0
    embed = atprotomodels.AppBskyEmbedImages.Main(images=[
        _make_atproto_image('/retrieved/fullimg.jpg', test_index=0)])
    assert post == ("This is a quick photo update.", embed, None)


def test_one_micropost_with_two_photos(cli, feedutil, bskymock, monkeypatch):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a photo update with 2 photos.</p>
<div>
    <a class="u-photo" href="/fullimg1.jpg"><img src="/thumbimg1.jpg"/></a>
    <a class="u-photo" href="/fullimg2.jpg"><img src="/thumbimg2.jpg"/></a>
</div>
<a class="u-url" href="/01234.html">permalink</a>"""
    ))

    cli.appendSiloConfig('test', 'bluesky')
    cli.setFeedConfig('feed', feed)
    bskymock.installCredentials(cli, 'test')

    with monkeypatch.context() as m:
        import silorider.silos.bluesky
        mock_urllib(m)
        m.setattr(silorider.silos.bluesky.BlueskySilo, 'mediaCallback',
                  _patched_media_callback)
        ctx, _ = cli.run('process')

    assert ctx.cache.wasPosted('test', '/01234.html')
    blob = ctx.silos[0].client.blobs[0]
    assert blob == ('/retrieved/fullimg1.jpg', None)
    blob = ctx.silos[0].client.blobs[1]
    assert blob == ('/retrieved/fullimg2.jpg', None)
    post = ctx.silos[0].client.posts[0]
    embed = atprotomodels.AppBskyEmbedImages.Main(images=[
        _make_atproto_image('/retrieved/fullimg1.jpg', test_index=0),
        _make_atproto_image('/retrieved/fullimg2.jpg', test_index=1)])
    assert post == ("This is a photo update with 2 photos.", embed, None)


def test_one_micropost_with_links(cli, feedutil, bskymock):
    cli.appendSiloConfig('test', 'bluesky')
    bskymock.installCredentials(cli, 'test')

    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="p-name">This is a link: http://example.org/blah</p>
<a class="u-url" href="/01234.html">permalink</a>"""))

    cli.setFeedConfig('feed', feed)
    ctx, _ = cli.run('process')
    post = ctx.silos[0].client.posts[0]
    assert post[0] == "This is a link: http://example.org/blah"
    assert post[2] == None

    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="e-content">This is another link: <a href="http://example.org/blah">http://example.org/blah</a></p>
<a class="u-url" href="/01234.html">permalink</a>"""))  # NOQA
    cli.setFeedConfig('feed', feed)
    ctx, _ = cli.run('process')
    post = ctx.silos[0].client.posts[0]
    assert post[0] == "This is another link: http://example.org/blah"  # NOQA
    facet = _make_link_facet('http://example.org/blah', 22, 45)
    assert post[2] == [facet]

    feed = cli.createTempFeed(feedutil.makeFeed(
        """<p class="e-content">This is yet <a href="http://example.org/blah">another link</a></p>
<a class="u-url" href="/01234.html">permalink</a>"""))  # NOQA
    cli.setFeedConfig('feed', feed)
    ctx, _ = cli.run('process')
    post = ctx.silos[0].client.posts[0]
    assert post[0] == "This is yet another link"  # NOQA
    facet = _make_link_facet('http://example.org/blah', 12, 24)
    assert post[2] == [facet]


def _make_link_facet(url, start, end):
    return atprotomodels.AppBskyRichtextFacet.Main(
        features=[atprotomodels.AppBskyRichtextFacet.Link(uri=url)],
        index=atprotomodels.AppBskyRichtextFacet.ByteSlice(
            byteStart=start, byteEnd=end),
        )


def _patched_media_callback(self, tmpfile, mt, url, desc):
    return self.client.upload_blob(tmpfile, desc)


@pytest.fixture(scope='session')
def bskymock():
    from silorider.silos.bluesky import BlueskySilo
    BlueskySilo._CLIENT_CLASS = BlueskyMock
    return BlueskyMockUtil()


def _make_atproto_image(link, alt="", mime_type="image/jpg", size=100, test_index=None):
    # atproto will validate models and that forces us to create
    # an actual Image object.
    # Not sure why we need to use model_validate here -- the simple
    # constructor with keywords throws a validation error :(
    blob_link = atprotomodels.blob_ref.BlobRefLink.model_validate({'$link': link})
    blob = atprotomodels.blob_ref.BlobRef(mime_type=mime_type, ref=blob_link, size=size)
    img = atprotomodels.AppBskyEmbedImages.Image(alt=alt, image=blob)
    if test_index is not None:
        img.__test_index = test_index
    return img


class BlueskyMock:
    def __init__(self, base_url):
        # base_url is unused here.
        self.posts = []
        self.blobs = []

    def login(self, email, password):
        assert email == 'TEST_EMAIL'
        assert password == 'TEST_PASSWORD'

    def upload_blob(self, tmpfile, desc):
        img = _make_atproto_image(tmpfile, test_index=len(self.blobs))
        self.blobs.append((tmpfile, desc))
        return img

    def send_post(self, text, post_datetime=None, embed=None, facets=None):
        self.posts.append((text, embed, facets))


class BlueskyMockUtil:
    def installCredentials(self, cli, silo_name):
        def do_install_credentials(ctx):
            ctx.cache.setCustomValue(
                '%s_email' % silo_name,
                'TEST_EMAIL')
            ctx.cache.setCustomValue(
                '%s_password' % silo_name,
                'TEST_PASSWORD')

        cli.preExecHook(do_install_credentials)
