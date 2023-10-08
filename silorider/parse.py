import os.path
import logging
import configparser
import urllib.request
import bs4
import mf2py
import dateutil.parser
from datetime import datetime, date, timezone, timedelta
from .config import has_lxml


logger = logging.getLogger(__name__)

default_dt = datetime.fromtimestamp(0, tz=timezone(timedelta(0)))


def _get_entry_published_dt(entry):
    dt = entry.get('published', default_dt)
    if isinstance(dt, date):
        dt = datetime.combine(dt, datetime.now().time())
    return dt


def parse_url(url_or_path, name, config):
    mf_obj = parse_mf2(url_or_path, name, config)
    matcher = EntryMatcher(mf_obj.to_dict(), mf_obj.__doc__)

    feed = Feed(url_or_path, matcher.mf_dict)

    entries = []
    for pair in matcher.entries:
        mf_entry, bs_el = pair
        try:
            entry = Entry(feed, mf_entry, bs_el)
            entry.interpret()
        except InvalidEntryException:
            logger.debug("Found invalid entry... skipping.")
            continue

        entries.append(entry)

    sorted_entries = sorted(
        entries,
        key=_get_entry_published_dt,
        reverse=False)

    feed.entries = sorted_entries
    logger.debug("Parsed %d entries for: %s" % (len(sorted_entries), url_or_path))
    return feed


def parse_mf2(url_or_path, name, config):
    # Get the URL or file contents.
    logger.debug("Fetching %s" % url_or_path)
    if os.path.exists(url_or_path):
        with open(url_or_path, 'r', encoding='utf8') as fp:
            html_raw = fp.read()
    else:
        with urllib.request.urlopen(url_or_path) as req:
            html_raw = req.read()

    # Load this into an HTML document and optionally patch it.
    html_doc = bs4.BeautifulSoup(
            html_raw,
            'lxml' if has_lxml else 'html5lib')
    _modify_html_doc(html_doc, name, config)

    # Parse the microformats!
    return mf2py.Parser(
            doc=html_doc,
            html_parser='html5lib',
            img_with_alt=True)


def _modify_html_doc(doc, name, config):
    try:
        class_mods = config.items('classes:%s' % name)
    except configparser.NoSectionError:
        return

    logger.debug("Modifying HTML doc:")
    for selector, to_add in class_mods:
        elems = list(doc.select(selector))
        if not elems:
            logger.warning("No elements matched by rule: %s" % selector)
            continue
        for elem in elems:
            logger.debug("Adding %s to %s" % (to_add, elem.name))
            if to_add == 'dt-published':
                _insert_html_datetime_published(doc, elem)
            else:
                if 'class' not in elem.attrs:
                    elem['class'] = []
                elem['class'].append(to_add)


def _insert_html_datetime_published(doc, elem):
    dt_str = str(elem.string)
    try:
        dt = dateutil.parser.parse(dt_str)
    except dateutil.parser.ParseError as err:
        logger.error("Can't parse published date: %s" % err)
        return

    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        now_time = datetime.now().time()
        dt = datetime.combine(dt.date(), now_time)

    time_el = doc.new_tag('time')
    time_el['class'] = ['dt-published']
    time_el['datetime'] = dt.isoformat(' ', 'seconds')
    time_el.append(dt_str)

    elem.clear()
    elem.append(time_el)
    logger.debug("Adding datetime attribute: %s" % dt)


class InvalidEntryException(Exception):
    pass


class Feed:
    def __init__(self, url, mf_dict):
        self.url = url
        self._mf_dict = mf_dict
        self.entries = []


class Entry:
    def __init__(self, owner_feed, mf_entry, bs_obj):
        self._owner_feed = owner_feed
        self._mf_entry = mf_entry
        self._bs_obj = bs_obj

        self._type = None
        self._props = None

    @property
    def entry_type(self):
        return self._type

    @property
    def html_element(self):
        return self._bs_obj

    def __getattr__(self, name):
        try:
            return self._doGet(name)
        except KeyError:
            raise AttributeError("Entry does not have property '%s'." % name)

    def get(self, name, default=None, *, force_list=False):
        try:
            return self._doGet(name, force_list=force_list)
        except KeyError:
            return default

    def _doGet(self, name, force_list=False):
        self.interpret()

        values = self._props[name]
        if not force_list and isinstance(values, list) and len(values) == 1:
            return values[0]
        return values

    def htmlFind(self, *args, **kwargs):
        if self._bs_obj is None:
            raise Exception("No HTML object is available for this entry.")

        return self._bs_obj.find(*args, **kwargs)

    def interpret(self):
        if self._type is not None or self._props is not None:
            return

        import mf2util

        self._type = mf2util.post_type_discovery(self._mf_entry)
        self._props = mf2util.interpret_entry(
            self._owner_feed._mf_dict, self._owner_feed.url,
            hentry=self._mf_entry)

        # Adds a `is_micropost` property.
        self._detect_micropost()

        # mf2util only detects the first photo for a "photo"-type post,
        # but there might be several so we need to fix that.
        #
        # mf2util also apparently doesn't always bring "category" info.
        self._fix_interpreted_props('photo', 'category')

    def _detect_micropost(self):
        is_micro = False
        name = self.get('name')
        content = self.get('content-plain')
        if content and not name:
            is_micro = True
        elif name and not content:
            is_micro = True
        elif name and content:
            shortest = min(len(name), len(content))
            is_micro = (name[:shortest] == content[:shortest])
        self._props['is_micropost'] = is_micro

    def _fix_interpreted_props(self, *names):
        for name in names:
            values = self._mf_entry['properties'].get(name, [])
            if isinstance(values, str):
                values = [values]
            self._props[name] = values


class EntryMatcher:
    """ A class that matches `mf2util` results along with the original
        BeautifulSoup document, so we have HTML objects on hand if needed.
    """
    def __init__(self, mf_dict, bf_doc):
        self.mf_dict = mf_dict
        self.entries = []

        els_by_type = {}
        next_el = {}

        items = mf_dict.get('items', [])
        for item in items:
            item_types = item.get('type', [])
            if 'h-feed' not in item_types:
                continue

            children = item.get('children', [])
            logger.debug("Matching %d feed items" % len(children))
            for e in children:
                e_types = e.get('type')
                if not e_types:
                    continue

                # We only look at the first type on any element.
                entry_type = e_types[0]

                # Get the list of all elements of that type from the doc.
                if entry_type not in els_by_type:
                    ebt = list(bf_doc.find_all(class_=entry_type))
                    els_by_type[entry_type] = ebt
                    next_el[entry_type] = 0
                    if len(ebt) == 0:
                        logger.warning("Found no elements of type: %s" % entry_type)

                # We figure that mf2py found elements in the same order as
                # they are found in the document, so we associate the two
                # in order.
                els = els_by_type[entry_type]
                try:
                    e_and_el = (e, els[next_el[entry_type]])
                    self.entries.append(e_and_el)
                except IndexError:
                    logger.error(
                            "Ran out of elements in document! Found %d elements "
                            "of type '%s' but was trying to get element %d" %
                            (len(els), str(e_types), next_el[entry_type]))
                next_el[entry_type] += 1


def strip_img_alt(photos):
    if not isinstance(photos, list):
        raise Exception("Expected list of media items, got: %s" % photos)
    urls = []
    for photo in photos:
        if isinstance(photo, dict):
            urls.append(photo['value'])
        elif isinstance(photo, str):
            urls.append(photo)
        else:
            raise Exception("Unexpected media item: %s" % photo)
    return urls
