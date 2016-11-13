# -*- coding: utf-8 -*-
"""
    extarget
    ~~~~~~~~

    Rewrite external hyperlinks to open in new tab/window.

    :copyright: Copyright 2014, Erigones, s. r. o.
    :license: BSD.
"""
import re

from docutils import nodes, utils

from sphinx.util.nodes import split_explicit_title


re_link = re.compile(r'(<a class="reference external") (href="https?://)')
link_repl = r'\1 target="_blank" \2'


def add_link_target(app, pagename, templatename, context, doctree):
    body = context.get('body', None)

    if body:
        context['body'] = re_link.sub(link_repl, body)


def setup(app):
    app.connect('html-page-context', add_link_target)
