from __future__ import annotations

from docutils import nodes

from sphinx.application import Sphinx
from sphinx.directives.admonitions import SphinxAdmonition
from sphinx.util.docutils import SphinxDirective, SphinxRole
from sphinx.util.typing import ExtensionMetadata


class TestCard(SphinxAdmonition):
    required_arguments = 1
    node_class = nodes.admonition
class RequirementCard(SphinxAdmonition):
    required_arguments = 1
    node_class = nodes.admonition
class Algorithm(SphinxAdmonition):
    required_arguments = 1
    node_class = nodes.admonition
class UseCase(SphinxAdmonition):
    required_arguments = 1
    node_class = nodes.admonition

def setup(app: Sphinx) -> ExtensionMetadata:
    app.add_directive('test-card', TestCard, override=True)
    app.add_directive('requirement', RequirementCard, override=True)
    app.add_directive('algorithm', Algorithm, override=True)
    app.add_directive('use-case', UseCase, override=True)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }