import datetime
import textwrap
from .base import Silo
from ..format import get_best_text


class PrintSilo(Silo):
    SILO_TYPE = 'print'

    def authenticate(self, ctx):
        pass

    def postEntry(self, entry, ctx):
        import pprint

        tokens = {}
        shorten = (self.getConfigItem('shorten', '').lower() in
                   ['true', 'yes', 'on', '1'])
        names = self.getConfigItem('items', 'best_text,category,published')
        names = names.split(',')
        for n in names:
            if n == 'type':
                tokens['type'] = entry.entry_type

            elif n == 'best_text':
                tokens['best_text'] = get_best_text(entry)

            else:
                v = entry.get(n)
                if shorten:
                    v = textwrap.shorten(v, width=400, placeholder='...')
                if isinstance(v, datetime.datetime):
                    v = v.strftime('%c')
                tokens[n] = v

        pprint.pprint(tokens)
