import re
import textwrap
import bs4
from .config import has_lxml


def format_entry(entry, limit=None, add_url='auto', url_flattener=None):
    url = entry.url

    ctx = HtmlStrippingContext()
    if url_flattener:
        ctx.url_flattener = url_flattener

    name = get_best_text(entry, ctx)
    if not name:
        raise Exception("Can't find best text for entry: %s" % url)

    do_add_url = ((add_url is True) or
                  (add_url == 'auto' and not entry.is_micropost))
    if limit:
        text_length = ctx.text_length
        if do_add_url and url:
            limit -= 1 + ctx.url_flattener.measureUrl(url)

        shortened = text_length > limit
        if shortened:
            # If we have to shorten the text, but we haven't taken the
            # URL into account yet, let's see if we have to include it now!
            # (this happens when we only want to include it when the text
            #  is shortened)
            if not do_add_url and add_url == 'auto' and url:
                do_add_url = True
                limit -= 1 + ctx.url_flattener.measureUrl(url)

        if limit <= 0:
            raise Exception("Can't shorten post name.")

        name = textwrap.shorten(name, width=limit, placeholder="...")

    if do_add_url and url:
        name += ' ' + url
    return name


class UrlFlattener:
    def replaceHref(self, text, url, ctx):
        raise NotImplementedError()

    def measureUrl(self, url):
        raise NotImplementedError()


class _NullUrlFlattener(UrlFlattener):
    def replaceHref(self, text, url, ctx):
        return None

    def measureUrl(self, url):
        return len(url)


URLMODE_INLINE = 0
URLMODE_LAST = 1
URLMODE_BOTTOM_LIST = 2

class HtmlStrippingContext:
    def __init__(self):
        self.url_mode = URLMODE_BOTTOM_LIST
        self.urls = []
        self.nosp_urls = []
        self.url_flattener = _NullUrlFlattener()
        self.text_length = 0



def get_best_text(entry, ctx=None, *, plain=True):
    elem = entry.htmlFind(class_='p-title')
    if not elem:
        elem = entry.htmlFind(class_='p-name')
    if not elem:
        elem = entry.htmlFind(class_='e-content')

    if elem:
        if not plain:
            text = '\n'.join([str(c) for c in elem.contents])
            return str(text)
        return strip_html(elem, ctx)

    return None


def strip_html(bs_elem, ctx=None):
    if isinstance(bs_elem, str):
        bs_elem = bs4.BeautifulSoup(bs_elem,
                                    'lxml' if has_lxml else 'html5lib')

    # Prepare stuff and run stripping on all HTML elements.
    outtxt = ''
    if ctx is None:
        ctx = HtmlStrippingContext()
    for c in bs_elem.children:
        outtxt += _do_strip_html(c, ctx)

    # If URLs are inline, insert them where we left our marker. If not, replace
    # our markers with an empty string and append the URLs at the end.
    keys = ['url:%d' % i for i in range(len(ctx.urls))]
    if ctx.url_mode == URLMODE_INLINE:
        url_repl = [' ' + u for u in ctx.urls]
        # Some URLs didn't have any text to be placed next to, so for those
        # we don't need any extra space before.
        for i in ctx.nosp_urls:
            url_repl[i] = url_repl[i][1:]
        urls = dict(zip(keys, url_repl))
    else:
        urls = dict(zip(keys, [''] * len(ctx.urls)))
    outtxt = outtxt % urls
    if ctx.url_mode != URLMODE_INLINE and ctx.urls:
        outtxt = outtxt.rstrip()
        if ctx.url_mode == URLMODE_LAST:
            outtxt += ' ' + ' '.join(ctx.urls)
        elif ctx.url_mode == URLMODE_BOTTOM_LIST:
            outtxt += '\n' + '\n'.join(ctx.urls)

    # Add the length of URLs to the text length.
    for url in ctx.urls:
        ctx.text_length += ctx.url_flattener.measureUrl(url)
    # Add spaces and other extra characters to the text length.
    if ctx.url_mode == URLMODE_INLINE:
        # One space per URL except the explicitly no-space-urls.
        ctx.text_length += len(ctx.urls) - len(ctx.nosp_urls)
    else:
        # One space or newline per URL, plus the first one.
        ctx.text_length += len(ctx.urls) + 1

    return outtxt


def _escape_percents(txt):
    return txt.replace('%', '%%')


def _do_strip_html(elem, ctx):
    if isinstance(elem, bs4.NavigableString):
        raw_txt = str(elem)
        ctx.text_length += len(raw_txt)
        return _escape_percents(raw_txt)

    if elem.name == 'a':
        try:
            href = elem['href']
        except KeyError:
            href = None
        cnts = list(elem.contents)
        if len(cnts) == 1:
            # Use the URL flattener to reformat the hyperlink.
            href_txt = cnts[0].string
            old_text_length = ctx.text_length
            href_flattened = ctx.url_flattener.replaceHref(href_txt, href, ctx)
            if href_flattened is not None:
                # We have a reformatted URL. Use that, but check if the
                # flattener computed a custom text length. If not, do the
                # standard computation.
                if ctx.text_length == old_text_length:
                    ctx.text_length += len(href_flattened)
                return href_flattened

            # If we have a simple hyperlink where the text is a substring of
            # the target URL, just return the URL.
            if href_txt in href:
                a_txt = '%%(url:%d)s' % len(ctx.urls)
                ctx.nosp_urls.append(len(ctx.urls))
                ctx.urls.append(href)
                # No text length to add.
                return a_txt

        # No easy way to simplify this hyperlink... let's put a marker
        # for the URL to be later replaced in the text.
        # Text length is accumulated through recursive calls to _do_strip_html.
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
        ctx.text_length += len(outtxt)
        return outtxt

    if elem.name == 'ul':
        outtxt = ''
        for c in elem.children:
            if c.name == 'li':
                outtxt += '- ' + _do_strip_html(c, ctx)
                outtxt += '\n'
        ctx.text_length += len(outtxt)
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
