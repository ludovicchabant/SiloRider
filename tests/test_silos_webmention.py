import unittest.mock
import requests


def test_one_article_no_mentions(cli, feedutil):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<h1 class="p-name">A new article</h1>
<div class="e-content">
<p>This is the abstract of the article.</p>
<p>Read more at <a class="u-url" href="https://example.org/a-new-article">permalink</a>.</p>
</div>
"""  # NOQA
    ))

    cli.appendSiloConfig('test', 'webmention', url='/blah')
    cli.setFeedConfig('feed', feed)

    with unittest.mock.patch('requests.get') as mock_get, \
            unittest.mock.patch('requests.post') as mock_post:
        mock_get.side_effect = [
            _MockResponse('')]
        mock_post.side_effect = []
        ctx, _ = cli.run('process')
        assert mock_get.call_args_list[0][0] == ('https://example.org/a-new-article',)  # NOQA


def test_one_article_one_mention(cli, feedutil):
    feed = cli.createTempFeed(feedutil.makeFeed(
        """<h1 class="p-name">A new article</h1>
<div class="e-content">
<p>This is the abstract of the article.</p>
<p>Read more at <a class="u-url" href="https://example.org/a-new-article">permalink</a>.</p>
</div>
"""  # NOQA
    ))

    cli.appendSiloConfig('test', 'webmention', url='/blah')
    cli.setFeedConfig('feed', feed)

    with unittest.mock.patch('requests.get') as mock_get, \
            unittest.mock.patch('requests.post') as mock_post:
        mock_get.side_effect = [
            _MockResponse("""
<p>This is a reply to <a href="https://other.org/article">another article<a>.</p>
"""),  # NOQA
            _MockResponse("""
<html><head>
    <link rel="webmention" href="https://other.org/webmention">
</head><body>
</body></html>""")]
        mock_post.side_effect = [
            _MockResponse('')]
        ctx, _ = cli.run('process')
        assert mock_get.call_args_list[0][0] == ('https://example.org/a-new-article',)  # NOQA
        assert mock_get.call_args_list[1][0] == ('https://other.org/article',)  # NOQA
        assert mock_post.call_args_list[0][0] == ('https://other.org/webmention',)  # NOQA


class _MockResponse:
    def __init__(self, txt):
        self.status_code = requests.codes.ok
        self.headers = {}
        self.history = []
        self.text = self.content = txt
