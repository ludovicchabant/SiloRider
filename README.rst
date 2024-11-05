
SiloRider
=========

SiloRider is a command-line utility that lets you implement the `POSSE`_ model
on a website. This is how it works:

- It reads your website's main page (or whatever URL you supply) and looks for
  `Microformats`_ markup.
- It reads a configuration file where you describe which "silos" (*i.e.*
  external services) you want to post your content to.
- It reads a local cache file to figure out which content has already been
  posted where, so it only posts new content.
- It actually posts that content to each silo.


Supported Silos
---------------

Right now, the following silos are supported:

- `Mastodon`_: an open, federated social network and microblogging service.
- `Bluesky`_: an open, federated social network and microblogging service.
- `Twitter`_: a proprietary social network and microblogging service.
- `Facebook`_: a proprietary social network and microblogging service.
- Print: a debug silo that just prints entries in the console.


Installation
------------

You can install SiloRider like any other Python tool::

  pip install silorider

You can then check it installed correctly with::

  silorider -h

You can also install from source by cloning the Git or Mercurial repository and
running::

  pip install -e /path/to/silorider/repo


Quickstart
----------

SiloRider will need to read a configuration file in `INI`_ format. The minimum
requirement is to define at least one "silo" using a ``silo:<name>`` section,
and to specify the url to one of your personal websites::

    [silo:my_mastodon]
    type: mastodon
    url: https://mastodon.social

    [urls]
    my_blog: https://your.website.com

This defines one Mastodon silo to which you want to cross-post entries from
your blog at ``your.website.com``.

You can then run::

    silorider auth my_mastodon 

This command will authenticate your Mastodon account and provide SiloRider with
the permission to post to your timeline. The authorization tokens are stored in
a cache file that defaults to ``silorider.db``, next to the configuration file.
Later, this cache will also contain the list of entries already posted to each
silo.

Once authenticated, you can run::

    silorider populate

This will populate the cache with the existing entries, since you probably
don't want the first run of SiloRider to cross-post your last dozen or so
entries in one go.

Later, when you post something new, you can then run::

    silorider process

This will pick up the new entries and post them to Mastodon. You can run this
command again regularly... if there's something new, SiloRider will cross-post
it to the configured silos. If not, it will just exit.


.. _POSSE: https://indieweb.org/POSSE
.. _Microformats: http://microformats.org/
.. _Mastodon: https://joinmastodon.org/
.. _Twitter: https://twitter.com/
.. _INI: https://en.wikipedia.org/wiki/INI_file

