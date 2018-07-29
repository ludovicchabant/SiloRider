
def mock_urllib(m):
    import urllib.request
    m.setattr(urllib.request, 'urlretrieve', _patched_urlretrieve)
    m.setattr(urllib.request, 'urlcleanup', _patched_urlcleanup)
    return m


def _patched_urlretrieve(url):
    return ('/retrieved/' + url.lstrip('/'), None)


def _patched_urlcleanup():
    pass
