"""Documentation for DE-Book."""

import os
import sys

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = "Tanglenomicon API"
copyright = "2023, temp"
author = "temp"
release = "0.0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    # "sphinx.ext.mathjax",
    "myst_parser",
    "sphinxcontrib.mermaid",
    "autodoc2",
    "sphinx_rtd_dark_mode",
]

templates_path = ["_templates"]
exclude_patterns = []
source_suffix = {".rst": "restructuredtext"}


suppress_warnings = ["myst.strikethrough", "misc.highlighting_failure"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.7", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
    "markdown_it": ("https://markdown-it-py.readthedocs.io/en/latest", None),
}

# -- Autodoc settings ---------------------------------------------------

autodoc2_packages = [
    {
        "path": "../tanglenomicon_data_api",
        "exclude_files": ["_docs.py"],
    }
]
autodoc2_hidden_objects = ["dunder", "private", "inherited"]
autodoc2_replace_annotations = [
    ("re.Pattern", "typing.Pattern"),
    ("markdown_it.MarkdownIt", "markdown_it.main.MarkdownIt"),
]
autodoc2_replace_bases = [
    ("sphinx.directives.SphinxDirective", "sphinx.util.docutils.SphinxDirective"),
]
autodoc2_render_plugin = "myst"

nitpicky = False


# -- MyST settings ---------------------------------------------------
myst_fence_as_directive = ["mermaid"]

myst_enable_extensions = [
    # "dollarmath",
    # "amsmath",
    "deflist",
    "fieldlist",
    "html_admonition",
    "html_image",
    "colon_fence",
    "smartquotes",
    "replacements",
    "linkify",
    "strikethrough",
    "substitution",
    "tasklist",
    "attrs_inline",
    "attrs_block",
]
myst_url_schemes = {
    "http": None,
    "https": None,
    "mailto": None,
    "ftp": None,
    "wiki": "https://en.wikipedia.org/wiki/{{path}}#{{fragment}}",
    "doi": "https://doi.org/{{path}}",
    "gh-pr": {
        "url": "https://github.com/executablebooks/MyST-Parser/pull/{{path}}#{{fragment}}",
        "title": "PR #{{path}}",
        "classes": ["github"],
    },
    "gh-issue": {
        "url": "https://github.com/executablebooks/MyST-Parser/issue/{{path}}#{{fragment}}",
        "title": "Issue #{{path}}",
        "classes": ["github"],
    },
    "gh-user": {
        "url": "https://github.com/{{path}}",
        "title": "@{{path}}",
        "classes": ["github"],
    },
}
myst_number_code_blocks = ["typescript"]
myst_heading_anchors = 2
myst_footnote_transition = True
# myst_dmath_double_inline = True
myst_enable_checkboxes = True
myst_substitutions = {
    "role": "[role](#syntax/roles)",
    "directive": "[directive](#syntax/directives)",
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
# user starts in dark mode
default_dark_mode = True
html_theme = "sphinx_rtd_theme"
# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "dracula"
# html_static_path = ["_static"]

mermaid_d3_zoom = True
mermaid_init_js = """mermaid.initialize({
  securityLevel: 'loose',
  theme: 'dark',
});"""


autosummary_generate = True
autoclass_content = "both"
html_show_sourcelink = False
autodoc_inherit_docstrings = True
