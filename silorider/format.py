import re
import textwrap


def format_entry(entry, limit=None, add_url='auto'):
    url = entry.url
    name = entry.best_name

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
