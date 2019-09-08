import re
import urllib.parse
import textwrap
import bs4
from .config import has_lxml


def format_entry(entry, limit=None, add_url='auto', url_flattener=None):
    url = entry.url
    name = get_best_text(entry, url_flattener=url_flattener)
    if not name:
        raise Exception("Can't find best text for entry: %s" % url)

    do_add_url = ((add_url is True) or
                  (add_url == 'auto' and not entry.is_micropost))
    if limit:
        if do_add_url and url:
            limit -= 1 + len(url)

        shortened = len(name) > limit
        if shortened:
            # If we have to shorten the text, but we haven't taken the
            # URL into account yet, let's see if we have to include now!
            # (this happens when we only want to include it when the text
            #  is shortened)
            if not do_add_url and add_url == 'auto' and url:
                do_add_url = True
                limit -= 1 + len(url)

        if limit <= 0:
            raise Exception("Can't shorten post name.")

        name = textwrap.shorten(name, width=limit, placeholder="...")

    if do_add_url and url:
        name += ' ' + url
    return name


class UrlFlattener:
    def replaceHref(self, text, url):
        return None


def get_best_text(entry, *, plain=True, inline_urls=True, url_flattener=None):
    elem = entry.htmlFind(class_='p-title')
    if not elem:
        elem = entry.htmlFind(class_='p-name')
    if not elem:
        elem = entry.htmlFind(class_='e-content')

    if elem:
        if not plain:
            text = '\n'.join([str(c) for c in elem.contents])
            return str(text)
        return strip_html(elem, inline_urls=inline_urls,
                          url_flattener=url_flattener)

    return None


def strip_html(bs_elem, *, inline_urls=True, url_flattener=None):
    if isinstance(bs_elem, str):
        bs_elem = bs4.BeautifulSoup(bs_elem,
                                    'lxml' if has_lxml else 'html5lib')

    outtxt = ''
    ctx = _HtmlStripping()
    ctx.url_flattener = url_flattener
    for c in bs_elem.children:
        outtxt += _do_strip_html(c, ctx)

    keys = ['url:%d' % i for i in range(len(ctx.urls))]
    if inline_urls:
        urls = dict(zip(keys, [' ' + u for u in ctx.urls]))
    else:
        urls = dict(zip(keys, [''] * len(ctx.urls)))
    outtxt = outtxt % urls
    if not inline_urls and ctx.urls:
        outtxt += '\n' + '\n'.join(ctx.urls)
    return outtxt


class _HtmlStripping:
    def __init__(self):
        self.urls = []
        self.url_flattener = None


def _escape_percents(txt):
    return txt.replace('%', '%%')


def _do_strip_html(elem, ctx):
    if isinstance(elem, bs4.NavigableString):
        return _escape_percents(str(elem))

    if elem.name == 'a':
        try:
            href = elem['href']
        except KeyError:
            href = None
        cnts = list(elem.contents)
        if len(cnts) == 1:
            href_txt = cnts[0].string
            if href_txt in href:
                # If we have a simple hyperlink where the text is a
                # substring of the target URL, just return the URL.
                return _escape_percents(href)

            if ctx.url_flattener:
                # Use an URL flattener if we have one.
                href_parsed = urllib.parse.urlparse(href)
                href_flattened = ctx.url_flattener.replaceHref(
                    href_txt, href_parsed)
                if href_flattened is not None:
                    return href_flattened

        # No easy way to simplify this hyperlink... let's put a marker
        # for the URL to be later replaced in the text.
        a_txt = ''.join([_do_strip_html(c, ctx)
                         for c in cnts])
        a_txt += '%%(url:%d)s' % len(ctx.urls)
        ctx.urls.append(href)
        return a_txt

    if elem.name == 'ol':
        outtxt = ''
        for i, c in enumerate(elem.children):
            if c.name == 'li':
                outtxt += ('%s. ' % (i + 1)) + _do_strip_html(c, ctx)
                outtxt += '\n'
        return outtxt

    if elem.name == 'ul':
        outtxt = ''
        for c in elem.children:
            if c.name == 'li':
                outtxt += '- ' + _do_strip_html(c, ctx)
                outtxt += '\n'
        return outtxt

    return ''.join([_do_strip_html(c, ctx) for c in elem.children])


re_sentence_end = re.compile(r'[\w\]\)\"\'\.]\.\s|[\?\!]\s')


def shorten_text(txt, limit):
    if len(txt) <= limit:
        return (txt, False)

    m = re_sentence_end.search(txt)
    if m and m.end <= (limit + 1):
        return (txt[:m.end - 1], True)

    shorter = textwrap.shorten(
        txt, width=limit, placeholder="...")
    return (shorter, True)
