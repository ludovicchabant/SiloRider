import os
import os.path
import logging
import argparse
import configparser
import coloredlogs


logger = logging.getLogger(__name__)


class ExecutionContext:
    def __init__(self, args, config, cache, silos):
        self.args = args
        self.config = config
        self.cache = cache
        self.silos = silos


def _setup_auth(parser):
    def _run(ctx):
        from .commands.auth import auth_silo
        auth_silo(ctx)

    parser.add_argument(
        'silo',
        action='append',
        help=("The name of the silo to authenticate. "
              "Use 'all' to authenticate all declared silos."))
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help="Force re-authenticate even silos with valid access.")
    parser.add_argument(
        '--console',
        action='store_true',
        help=("Use the current terminal to enter credentials. This is "
              "useful if you're not in an environment where silorider can "
              "launch a browser."))
    parser.set_defaults(func=_run)


def _setup_process(parser):
    def _run(ctx):
        from .commands.process import process_urls
        process_urls(ctx)

    parser.add_argument(
        '-u', '--url',
        action='append',
        help="Only parse the given URL name(s).")
    parser.add_argument(
        '-s', '--silo',
        action='append',
        help="Only use the given silo(s).")
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help="Ignore the cache, post all entries that qualify.")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Only report what would be posted, but don't post anything.")
    parser.set_defaults(func=_run)


def _setup_populate(parser):
    def _run(ctx):
        from .commands.utils import populate_cache
        populate_cache(ctx)

    parser.add_argument(
        '-u', '--url',
        action='append',
        help="Only populate from the given URL name(s).")
    parser.add_argument(
        '-s', '--silo',
        action='append',
        help="Only populate the given silo(s).")
    parser.add_argument(
        '--until',
        help="The date until which to populate the cache (included).")
    parser.set_defaults(func=_run)


commands = {
    'auth': {
        'help': "Authenticate with a silo service.",
        'setup': _setup_auth,
    },
    'process': {
        'help': "Post a website's latest articles to silo services.",
        'setup': _setup_process,
    },
    'populate': {
        'help': "Populates the cache with the latest entries from a feed.",
        'setup': _setup_populate,
    }
}


has_debug_logging = False
pre_exec_hook = None
post_exec_hook = None


def _unsafe_main(args=None):
    parser = argparse.ArgumentParser('SiloRider')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Print debug messages.")
    parser.add_argument(
        '--no-color',
        action='store_true',
        help="Don't use pretty colors.")
    parser.add_argument(
        '-c', '--config',
        help="Configuration file to load.")

    subparsers = parser.add_subparsers()
    for cn, cd in commands.items():
        cp = subparsers.add_parser(cn, help=cd.get('help'))
        cd['setup'](cp)

    args = parser.parse_args(args)

    global has_debug_logging
    has_debug_logging = args.verbose

    if not args.no_color:
        coloredlogs.install()

    loglvl = logging.DEBUG if args.verbose else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(loglvl)
    for handler in root_logger.handlers:
        handler.setLevel(loglvl)

    if not getattr(args, 'func', None):
        parser.print_help()
        return

    logger.debug("Loading configuration.")
    xdg_config_home = os.getenv('XDG_CONFIG_HOME',
                                os.path.expanduser('~/.config'))
    config = configparser.ConfigParser(interpolation=None)
    config_paths = [
        os.path.join(os.path.dirname(__file__), 'default.cfg'),
        os.path.join(xdg_config_home, 'silorider/silorider.cfg')
    ]
    if args.config:
        config_paths.append(args.config)
    config.read(config_paths)

    from .silos.base import has_any_silo
    if not has_any_silo(config):
        logger.warning("No silos defined in the configuration file. "
                       "Nothing to do!")
        return
    if not config.has_section('urls') or not config.items('urls'):
        logger.warning("No URLs defined in the configuration file. "
                       "Nothing to do!")
        return

    logger.debug("Initializing cache.")
    from .cache.base import load_cache
    cfg_dir = os.path.dirname(args.config) if args.config else None
    cache = load_cache(config, cfg_dir)

    logger.debug("Initializing silo riders.")
    from .silos.base import load_silos
    silos = load_silos(config, cache)

    ctx = ExecutionContext(args, config, cache, silos)

    if pre_exec_hook:
        pre_exec_hook(ctx)

    res = args.func(ctx)

    if post_exec_hook:
        post_exec_hook(ctx, res)

    if isinstance(res, int):
        return res
    return 0


def main():
    try:
        res = _unsafe_main()
    except Exception as ex:
        if has_debug_logging:
            raise
        logger.error(ex)
        res = 1

    import sys
    sys.exit(res)


if __name__ == '__main__':
    main()
