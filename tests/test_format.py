import pytest
from silorider.format import format_entry


test_url = 'https://example.org/article'


class TestEntry:
    pass


def _make_test_entry(best_name, is_micropost):
    entry = TestEntry()
    entry.best_name = best_name
    entry.is_micropost = is_micropost
    entry.url = test_url
    return entry


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
def test_format_lonform_entry(title, limit, add_url, expected):
    entry = _make_test_entry(title, False)
    actual = format_entry(entry, limit, add_url)
    assert actual == expected


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
    actual = format_entry(entry, limit, add_url)
    assert actual == expected
