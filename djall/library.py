import django.template

register = django.template.Library()

@register.tag
def ewregion(parser, token):
    return django.utils.safestring.mark_safe(
        '<!-- This is an ew region -->')


