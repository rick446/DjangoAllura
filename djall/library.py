from pylons import g, c
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

class EWRegionNode(template.Node):

    def __init__(self, name):
        self.name = name

    def render(self, context):
        result = list(g.resource_manager.emit(self.name))
        return mark_safe(''.join(result))

class DoNode(template.Node):

    def __init__(self, statement):
        self.statement = statement

    def render(self, context):
        exec self.statement in dict(context.dicts[-1], g=g, c=c)
        return ''

@register.tag
def ewregion(parser, token):
    contents = token.split_contents()
    try:
        tag, region = contents
    except ValueError:
        raise template.TemplateSyntaxError(
            '%s requires a single argument' % contents[0])
    return EWRegionNode(region)

@register.tag
def do(parser, token):
    contents = token.split_contents()
    try:
        tag, statement = contents
    except ValueError:
        raise template.TemplateSyntaxError(
            '%s requires a single argument' % contents[0])
    return DoNode(statement)


