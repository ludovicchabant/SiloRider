import pytest
from silorider.format import (
        format_entry, strip_html, HtmlStrippingContext,
        URLMODE_INLINE, URLMODE_LAST, URLMODE_BOTTOM_LIST)


test_url = 'https://example.org/article'


def _make_test_entry(best_name, is_micropost):
    class TestEntry:
        def __init__(self):
            self.is_micropost = is_micropost
            self.url = test_url

        def get(self, _):
            return best_name

        def htmlFind(self, *args, **kwargs):
            return best_name

    entry = TestEntry()
    return entry


@pytest.mark.parametrize("text, expected", [
    ("<p>Something</p>",
     "Something"),
    ("<p>Something with <em>emphasis</em> in it</p>",
     "Something with emphasis in it"),
    ("<p>Something with <a href=\"http://example.org/blah\">a link</a>",
     "Something with a link http://example.org/blah"),
    ("<p>Something with a link <a href=\"http://example.org/blah\">http://example.org</a>",  # NOQA
     "Something with a link http://example.org/blah"),
    ("<p>Something with <a href=\"http://example.org/first\">one link here</a> and <a href=\"http://example.org/second\">another there</a>...</p>",  # NOQA
     "Something with one link here http://example.org/first and another there http://example.org/second...")  # NOQA
])
def test_strip_html(text, expected):
    ctx = HtmlStrippingContext()
    ctx.url_mode = URLMODE_INLINE
    actual = strip_html(text, ctx)
    print(actual)
    print(expected)
    assert actual == expected


@pytest.mark.parametrize("text, expected", [
    ("<p>Something with <a href=\"http://example.org/blah\">a link</a></p>",
     "Something with a link\nhttp://example.org/blah"),
    ("<p>Something with a link <a href=\"http://example.org/blah\">http://example.org</a></p>",  # NOQA
     "Something with a link\nhttp://example.org/blah"),
    ("<p>Something with <a href=\"http://example.org/first\">one link here</a> and <a href=\"http://example.org/second\">another there</a>...</p>",  # NOQA
     "Something with one link here and another there...\nhttp://example.org/first\nhttp://example.org/second")  # NOQA
])
def test_strip_html_with_bottom_urls(text, expected):
    ctx = HtmlStrippingContext()
    ctx.url_mode = URLMODE_BOTTOM_LIST
    actual = strip_html(text, ctx)
    print(actual)
    print(expected)
    assert actual == expected


@pytest.mark.parametrize("title, limit, add_url, expected", [
    ('A test entry', None, False, 'A test entry'),
    ('A test entry', None, 'auto', 'A test entry ' + test_url),
    ('A test entry', None, True, 'A test entry ' + test_url),

    ('A test entry', 80, False, 'A test entry'),
    ('A test entry', 80, 'auto', 'A test entry ' + test_url),
    ('A test entry', 80, True, 'A test entry ' + test_url),

    ('A test entry that is very very long because its title has many many '
     'words in it for no good reason', 80, False,
     'A test entry that is very very long because its title has many many '
     'words in...'),
    ('A test entry that is very very long because its title has many many '
     'words in it for no good reason', 80, 'auto',
     'A test entry that is very very long because its... ' + test_url),
    ('A test entry that is very very long because its title has many many '
     'words in it for no good reason', 80, True,
     'A test entry that is very very long because its... ' + test_url)
])
def test_format_longform_entry(title, limit, add_url, expected):
    entry = _make_test_entry(title, False)
    actual = format_entry(entry, limit=limit, add_url=add_url)
    assert actual.text == expected


@pytest.mark.parametrize("text, limit, add_url, expected", [
    ('A test entry', None, False, 'A test entry'),
    ('A test entry', None, 'auto', 'A test entry'),
    ('A test entry', None, True, 'A test entry ' + test_url),

    ('A test entry', 80, False, 'A test entry'),
    ('A test entry', 80, 'auto', 'A test entry'),
    ('A test entry', 80, True, 'A test entry ' + test_url),

    ('A test entry that is very very long because its title has many many '
     'words in it for no good reason', 80, False,
     'A test entry that is very very long because its title has many many '
     'words in...'),
    ('A test entry that is very very long because its title has many many '
     'words in it for no good reason', 80, 'auto',
     'A test entry that is very very long because its... ' + test_url),
    ('A test entry that is very very long because its title has many many '
     'words in it for no good reason', 80, True,
     'A test entry that is very very long because its... ' + test_url)
])
def test_format_micropost_entry(text, limit, add_url, expected):
    entry = _make_test_entry(text, True)
    actual = format_entry(entry, limit=limit, add_url=add_url)
    assert actual.text == expected
