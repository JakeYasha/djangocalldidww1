from django import template

register = template.Library()

@register.filter
def get_field(form, field_name):
    """
    Возвращает поле формы по имени
    """
    return form[field_name]
