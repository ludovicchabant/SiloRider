
feed1 = """
<html><body>
    <article class="h-entry">
      <h1 class="p-name">A new article</h1>
      <div class="e-content">
        <p>This is the text of the article.</p>
        <p>It has 2 paragraphs.</p>
      </div>
      <a class="u-url" href="https://example.org/a-new-article">permalink</a>
    </article>
</body></html>"""


def test_populate(cli):
    cli.appendSiloConfig('test', 'print', items='name')
    feed = cli.createTempFeed(feed1)
    ctx, _ = cli.run('populate', feed, '-s', 'test')
    assert ctx.cache.wasPosted('test', 'https://example.org/a-new-article')


feed2 = """
<html><body>
    <article class="h-entry">
      <h1 class="p-name">First article</h1>
      <div><time class="dt-published" datetime="2018-01-07T09:30:00-00:00"></time></div>
      <a class="u-url" href="https://example.org/first-article">permalink</a>
    </article>
    <article class="h-entry">
      <h1 class="p-name">Second article</h1>
      <div><time class="dt-published" datetime="2018-01-08T09:30:00-00:00"></time></div>
      <a class="u-url" href="https://example.org/second-article">permalink</a>
    </article>
    <article class="h-entry">
      <h1 class="p-name">Third article</h1>
      <div><time class="dt-published" datetime="2018-01-09T09:30:00-00:00"></time></div>
      <a class="u-url" href="https://example.org/third-article">permalink</a>
    </article>
</body></html>"""  # NOQA


def test_populate_until(cli):
    cli.appendSiloConfig('test', 'print', items='name')
    feed = cli.createTempFeed(feed2)
    ctx, _ = cli.run('populate', feed, '-s', 'test', '--until', '2018-01-08')
    assert ctx.cache.wasPosted('test', 'https://example.org/first-article')
    assert ctx.cache.wasPosted('test', 'https://example.org/second-article')
    assert not ctx.cache.wasPosted('test', 'https://example.org/third-article')
