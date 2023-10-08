import re
import string
import logging
import urllib.request
import textwrap
import bs4
from .config import has_lxml


logger = logging.getLogger(__name__)


def format_entry(entry, *, limit=None, card_props=None,
                 add_url='auto', url_flattener=None, url_mode=None):
    url = entry.url

    ctx = HtmlStrippingContext()
    if url_flattener:
        ctx.url_flattener = url_flattener
    if url_mode is not None:
        ctx.url_mode = url_mode
    # Don't add the limit yet.

    card = None

    # See if we can use a nice blurb for articles instead of their title.
    if card_props and not entry.is_micropost:
         card = get_card_info(entry, card_props, ctx)

    # Otherwise, find the best text, generally the title of the article, or the
    # text of the micropost.
    if card is None:
        best_text = get_best_text(entry, ctx)
        if best_text:
            card = CardInfo(entry, best_text, None, 'best_text')

    if not card:
        raise Exception("Can't find best text for entry: %s" % url)

    # We need to add the URL to the output if we were told to, or if we
    # are dealing with an article.
    do_add_url = ((add_url is True) or
                  (add_url == 'auto' and not entry.is_micropost))
    if limit:
        text_length = ctx.text_length
        if do_add_url and url:
            # We need to add the URL at the end of the post, so account
            # for it plus a space by making the text length limit smaller.
            limit -= 1 + ctx.url_flattener.measureUrl(url)

        shortened = text_length > limit
        if shortened:
            if not do_add_url and add_url == 'auto' and url:
                do_add_url = True
                limit -= 1 + ctx.url_flattener.measureUrl(url)

            if card.is_from == 'best_text':
                # We need to shorten the text! We can't really reason about it
                # anymore at this point because we could have URLs inside the
                # text that don't measure the correct number of characters
                # (such as with Twitter's URL shortening). Let's just start
                # again with a limit that's our max limit, minus the room
                # needed to add the link to the post.
                ctx = HtmlStrippingContext()
                ctx.limit = limit
                if url_flattener:
                    ctx.url_flattener = url_flattener
                card.text = get_best_text(entry, ctx)
            else:
                # We need to shorten the blurb! We can't do much else besides
                # truncate it...
                card.text = card.text[:limit]

    # Actually add the url to the original post now.
    if do_add_url and url:
        card.text += ' ' + url
    return card


class CardProps:
    def __init__(self, meta_attr, namespace):
        self.meta_attr = meta_attr
        self.namespace = namespace
        self.description = '%s:description' % namespace
        self.image = '%s:image' % namespace


class CardInfo:
    def __init__(self, entry, txt, img, from_label=None):
        self.entry = entry
        self.text = txt
        self.image = img
        self.is_from = from_label


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
URLMODE_ERASE = 3

class HtmlStrippingContext:
    def __init__(self):
        # Mode for inserting URLs
        self.url_mode = URLMODE_LAST
        # List of URLs to insert
        self.urls = []
        # Indices of URLs that should not get a leading whitespace
        self.nosp_urls = []
        # Object that can measure and shorten URLs
        self.url_flattener = _NullUrlFlattener()
        # Limit for how long the text can be
        self.limit = -1

        # Accumulated text length when accounting for shortened URLs
        self.text_length = 0
        # Same, but computed in bytes, as per UTF8 encoding
        self.byte_length = 0
        # Whether limit was reached
        self.limit_reached = False

    def processText(self, txt, allow_shorten=True):
        added_len = len(txt)
        next_text_length = self.text_length + added_len
        if self.limit <= 0 or next_text_length <= self.limit:
            self.text_length = next_text_length
            self.byte_length += len(txt.encode())
            return txt

        if allow_shorten:
            max_allowed = self.limit - self.text_length
            short_txt = textwrap.shorten(
                txt,
                width=max_allowed,
                expand_tabs=False,
                replace_whitespace=False,
                placeholder="...")
            self.text_length += len(short_txt)
            self.byte_length += len(short_txt.encode())
            self.limit_reached = True
            return short_txt
        else:
            self.limit_reached = True
            return ''


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


def get_card_info(entry, card_props, ctx):
    logger.debug("Downloading entry page to check meta entries: %s" % entry.url)
    with urllib.request.urlopen(entry.url) as req:
        raw_html = req.read()

    bs_html = bs4.BeautifulSoup(raw_html,
            'lxml' if has_lxml else 'html5lib')
    head = bs_html.find('head')

    desc_meta = head.find('meta', attrs={card_props.meta_attr: card_props.description})
    desc = desc_meta.attrs.get('content') if desc_meta else None

    img_meta = head.find('meta', attrs={card_props.meta_attr: card_props.image})
    img = img_meta.attrs.get('content') if img_meta else None

    if desc:
        logger.debug("Found card info, description: %s (image: %s)" % (desc, img))
        ctx.text_length = len(desc)
        return CardInfo(entry, desc, img, 'card')
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
    # If we reached the limit with the text alone, replace URLs with empty
    # strings and bail out.
    keys = ['url:%d' % i for i in range(len(ctx.urls))]
    if not ctx.limit_reached and ctx.url_mode == URLMODE_INLINE:
        url_repl = [' ' + u for u in ctx.urls]
        # Some URLs didn't have any text to be placed next to, so for those
        # we don't need any extra space before.
        for i in ctx.nosp_urls:
            url_repl[i] = url_repl[i][1:]
        urls = dict(zip(keys, url_repl))
    else:
        urls = dict(zip(keys, [''] * len(ctx.urls)))
    outtxt = outtxt % urls
    if ctx.limit_reached:
        return outtxt
    if ctx.urls:
        if ctx.url_mode == URLMODE_LAST:
            # Don't add unnecessary whitespace.
            # NOTE: our final measure of the text might be one character
            #       too long because of this, but that's desirable.
            if outtxt[-1] not in string.whitespace:
                outtxt += ' '
            outtxt += ' '.join(ctx.urls)
        elif ctx.url_mode == URLMODE_BOTTOM_LIST:
            # If the last character of the text is a whitespace, replace
            # it with a newline.
            # NOTE: our final measure of the text might be one character
            #       too long because of this, but that's desirable.
            if outtxt[-1] in string.whitespace:
                outtxt = outtxt[:-1] + '\n'
            else:
                outtxt += '\n'
            outtxt += '\n'.join(ctx.urls)
    # else, if url_mode is URLMODE_ERASE, don't do anything: we have
    # removed the markers and don't need to add the URLs anywhere.

    if ctx.url_mode != URLMODE_ERASE:
        # Add the length of URLs to the text length.
        for url in ctx.urls:
            url_len = ctx.url_flattener.measureUrl(url)
            ctx.text_length += url_len
            ctx.byte_length += url_len
        # Add spaces and other extra characters to the text length.
        if ctx.url_mode == URLMODE_INLINE:
            # One space per URL except the explicitly no-space-urls.
            added_spaces = len(ctx.urls) - len(ctx.nosp_urls)
            ctx.text_length += added_spaces
            ctx.byte_length += added_spaces
        else:
            # One space or newline per URL.
            added_spaces = len(ctx.urls)
            ctx.text_length += added_spaces
            ctx.byte_length += added_spaces
    return outtxt


def _escape_percents(txt):
    return txt.replace('%', '%%')


tags_valid_for_whitespace = {
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p'
}


def _do_strip_html(elem, ctx):
    if isinstance(elem, bs4.NavigableString):
        # We have some text.
        # We generally include this text without any alteration except when
        # the string is entirely whitespace. In that case, we only include
        # it if it's inside a valid text tag like <p>. Otherwise, it's
        # most likely whitespace inside html markup, such as indenting and
        # newlines between html tags.
        include_this = True
        raw_txt = str(elem)
        if raw_txt.isspace():
            include_this = False
            for p in elem.parents:
                if p and p.name in tags_valid_for_whitespace:
                    include_this = True
                    break

        if include_this:
            return _escape_percents(ctx.processText(raw_txt))
        else:
            return ''

    if elem.name == 'a':
        try:
            href = elem['href']
        except KeyError:
            href = None

        # Get the text under the hyperlink.
        cnts = list(elem.contents)
        if len(cnts) == 1:
            a_txt = cnts[0].string
        else:
            a_txt = ''.join([_do_strip_html(c, ctx)
                             for c in cnts])

        # Use the URL flattener to reformat the hyperlink.
        old_text_length = ctx.text_length
        href_flattened = ctx.url_flattener.replaceHref(a_txt, href, ctx)
        if href_flattened is not None:
            # We have a reformatted URL. Use that, but check if the
            # flattener computed a custom text length. If not, do the
            # standard computation.
            if ctx.text_length == old_text_length:
                return ctx.processText(href_flattened, False)
            return href_flattened

        # If we have a simple hyperlink where the text is a substring of
        # the target URL, just return the URL.
        if a_txt in href:
            if ctx.url_mode != URLMODE_ERASE:
                a_txt = '%%(url:%d)s' % len(ctx.urls)
                ctx.nosp_urls.append(len(ctx.urls))
                ctx.urls.append(href)
                # No text length to add.
                return a_txt
            else:
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
        return ctx.processText(outtxt)

    if elem.name == 'ul':
        outtxt = ''
        for c in elem.children:
            if c.name == 'li':
                outtxt += '- ' + _do_strip_html(c, ctx)
                outtxt += '\n'
        return ctx.processText(outtxt)

    if elem.name == 'p':
        # Add a newline before starting a paragraph only if this isn't
        # the first paragraph or piece of content.
        p_txt = ''
        if ctx.text_length > 0:
            p_txt = '\n'
        for c in elem.children:
            p_txt += _do_strip_html(c, ctx)
        return p_txt

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
