import io
import os
import os.path
import re
import logging
import tempfile
import pytest
import silorider.main


# def pytest_collect_file(parent, path):
#     if path.ext == ".html" and path.basename.startswith("feeds"):
#         return FeedFile(path, parent)


re_feed_test_sep = re.compile(r'^---$')


class FeedFile(pytest.File):
    def collect(self):
        with self.fspath.open() as fp:
            markup = fp.read()

        name = self.fspath.basename
        html_markup, yaml_markup = re_feed_test_sep.split(markup, 1)
        yield FeedItem(name, self, html_markup, yaml_markup)


class FeedItem(pytest.Item):
    def __init__(self, name, parent, in_spec, out_spec):
        super().__init__(name, parent)
        self.in_spec = in_spec
        self.out_spec = out_spec

    def runtest(self):
        pass


@pytest.fixture
def cli():
    return CliRunner()


class CliRunner:
    def __init__(self):
        self._cfgtxt = """
[cache]
uri=memory://for_test
"""
        self._pre_hooks = []
        self._cleanup = []

    def getFeedPath(self, name):
        return os.path.join(os.path.dirname(__file__),
                            'feeds',
                            '%s.html' % name)

    def createTempFeed(self, contents):
        tmpfd, tmpname = tempfile.mkstemp()
        with os.fdopen(tmpfd, 'w', encoding='utf8') as tmpfp:
            tmpfp.write(contents)
        self._cleanup.append(tmpname)
        return tmpname

    def setConfig(self, cfgtxt):
        self._cfgtxt = cfgtxt
        return self

    def appendConfig(self, cfgtxt):
        self._cfgtxt += cfgtxt
        return self

    def appendSiloConfig(self, silo_name, silo_type, **options):
        cfgtxt = '[silo:%s]\n' % silo_name
        cfgtxt += 'type=%s\n' % silo_type
        if options is not None:
            for n, v in options.items():
                cfgtxt += '%s=%s\n' % (n, v)
        return self.appendConfig(cfgtxt)

    def preExecHook(self, hook):
        self._pre_hooks.append(hook)

    def run(self, *args):
        pre_args = []
        if self._cfgtxt:
            tmpfd, tmpcfg = tempfile.mkstemp()
            print("Creating temporary configuration file: %s" % tmpcfg)
            with os.fdopen(tmpfd, 'w') as tmpfp:
                tmpfp.write(self._cfgtxt)
            self._cleanup.append(tmpcfg)
            pre_args = ['-c', tmpcfg]

        captured = io.StringIO()
        handler = logging.StreamHandler(captured)
        handler.setLevel(logging.INFO)
        silorider_logger = logging.getLogger('silorider')
        silorider_logger.addHandler(handler)

        main_ctx = None
        main_res = None

        def pre_exec_hook(ctx):
            for h in self._pre_hooks:
                h(ctx)

        def post_exec_hook(ctx, res):
            nonlocal main_ctx, main_res
            main_ctx = ctx
            main_res = res

        silorider.main.pre_exec_hook = pre_exec_hook
        silorider.main.post_exec_hook = post_exec_hook

        args = pre_args + list(args)
        print("Running command: %s" % list(args))
        try:
            silorider.main._unsafe_main(args)
        finally:
            silorider.main.pre_exec_hook = None
            silorider.main.post_exec_hook = None

            silorider_logger.removeHandler(handler)

            print("Cleaning %d temporary files." % len(self._cleanup))
            for tmpname in self._cleanup:
                os.remove(tmpname)

        return main_ctx, main_res


@pytest.fixture
def feedutil():
    return FeedUtil()


class FeedUtil:
    def makeFeed(self, *entries):
        feed = '<html><body>\n'
        for e in entries:
            feed += '<article class="h-entry">\n'
            feed += e
            feed += '</article>\n'
        feed += '</body></html>'
        return feed
