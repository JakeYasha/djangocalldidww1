from django import template

register = template.Library()

@register.filter
def get(obj, key):
    """
    Returns the value of the specified attribute of an object
    """
    try:
        return obj[key]
    except (KeyError, TypeError):
        try:
            return getattr(obj, key)
        except AttributeError:
            return ''
