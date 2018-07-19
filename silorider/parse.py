import os.path
import logging
import datetime


logger = logging.getLogger(__name__)


def parse_url(url_or_path):
    mf_obj = parse_mf2(url_or_path)
    matcher = EntryMatcher(mf_obj)

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
        key=lambda e: e.get(
            'published', datetime.datetime.fromtimestamp(
                0,
                tz=datetime.timezone(datetime.timedelta(0)))),
        reverse=False)

    feed.entries = sorted_entries
    return feed


def parse_mf2(url_or_path):
    import mf2py
    logger.debug("Fetching %s..." % url_or_path)
    if os.path.exists(url_or_path):
        obj = open(url_or_path, 'r', encoding='utf8')
        params = {'doc': obj}
    else:
        params = {'url': url_or_path}
    return mf2py.Parser(html_parser='html5lib', **params)


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

    @property
    def best_name(self):
        self.interpret()

        for pn in ['title', 'name', 'content-plain', 'content']:
            pv = self._props.get(pn)
            if pv:
                return pv
        return None

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
    def __init__(self, mf_obj):
        self.mf_dict = mf_obj.to_dict()
        self.entries = []

        els_by_type = {}
        next_el = {}
        bf = mf_obj.__doc__
        for e in self.mf_dict.get('items', []):
            types = e.get('type')
            if not types:
                continue

            entry_type = types[0]
            if entry_type not in els_by_type:
                ebt = list(bf.find_all(class_=entry_type))
                els_by_type[entry_type] = ebt
                next_el[entry_type] = 0

            els = els_by_type[entry_type]
            e_and_el = (e, els[next_el[entry_type]])
            self.entries.append(e_and_el)
            next_el[entry_type] += 1
