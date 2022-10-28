# Tommi Lahtonen 8.2.2022: fixed PolyglotForm compatibility with wtforms 3.0.1 and FlaskForm 
from __future__ import unicode_literals
#from wtforms.form import Form
from flask_wtf import FlaskForm

try:
    from html import escape
    from html.parser import HTMLParser
except ImportError:
    from cgi import escape
    from HTMLParser import HTMLParser

from wtforms.meta import DefaultMeta
#from wtforms.widgets.core import HTMLString
#from markupsafe import escape
from markupsafe import Markup

class PolyglotHTMLParser(HTMLParser):
    """This simplified ``HTMLParser`` converts its input to polyglot HTML.

    It works by making sure that stand-alone tags like ``<input>`` have a
    slash before the closing angle bracket, that attribute values are always
    quoted, and that boolean attributes have their value set to the attribute
    name (e.g., ``checked="checked"``).

    Note: boolean attributes are simply identified as attributes with no value
    at all.  Specifically, an attribute with an empty string (e.g.,
    ``checked=""``) will *not* be identified as boolean attribute, i.e., there
    is no semantic intelligence involved.

    >>> parser = PolyglotHTMLParser()
    >>> parser.feed('''<input type=checkbox name=foo value=y checked>''')
    >>> print(parser.get_output())
    <input type="checkbox" name="foo" value="y" checked="checked" />

    """

    def __init__(self):
        HTMLParser.__init__(self)
        self.reset()
        self.output = []

    def html_params(self, attrs):
        output = []
        for key, value in attrs:
            if value is None:
                value = key
            output.append(' {}="{}"'.format(key, escape(value, quote=True)))
        return ''.join(output)

    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            return self.handle_startendtag(tag, attrs)
        self.output.append('<{}{}>'.format(tag, self.html_params(attrs)))

    def handle_endtag(self, tag):
        self.output.append('</{}>'.format(tag))

    def handle_startendtag(self, tag, attrs):
        self.output.append('<{}{} />'.format(tag, self.html_params(attrs)))

    def handle_data(self, data):
        self.output.append(data)

    def handle_entityref(self, name):
        self.output.append('&{};'.format(name))

    def handle_charref(self, name):
        self.output.append('&#{};'.format(name))

    def get_output(self):
        return ''.join(self.output)


class PolyglotForm(FlaskForm):
    """
    Base form class which renders its fields using polyglot HTML5 output.
    """

    class PolyglotMeta(FlaskForm.Meta):
        """
        This meta class works exactly like ``DefaultMeta``, except that fields of
        forms using this meta class will output polyglot markup.
        """

        def render_field(self, field, render_kw):
            """
            Render a widget, and convert its output to polyglot HTML.
            """
            other_kw = getattr(field, 'render_kw', None)
            if other_kw is not None:
                render_kw = dict(other_kw, **render_kw)
            html = field.widget(field, **render_kw)
            parser = PolyglotHTMLParser()
            parser.feed(html)
            output = Markup(parser.get_output())
            return output


    Meta = PolyglotMeta
