from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def get_attr(obj, name):
    """Resolve dotted attributes/properties, including callables."""
    value = obj
    for part in str(name).split('.'):
        if value is None:
            return ''
        try:
            value = getattr(value, part)
        except (AttributeError, TypeError):
            return ''
        if callable(value):
            try:
                value = value()
            except TypeError:
                return value
    return value


@register.filter
def money(value):
    try:
        return f'{Decimal(value):,.2f}'
    except (InvalidOperation, TypeError, ValueError):
        return value


@register.filter
def percent(value):
    try:
        return f'{float(value):.1f}%'
    except (TypeError, ValueError):
        return value


@register.filter
def status_class(value):
    mapping = {
        'active': 'success',
        'present': 'success',
        'paid': 'success',
        'reviewed': 'success',
        'graded': 'success',
        'graduated': 'info',
        'submitted': 'info',
        'late': 'warning',
        'on_leave': 'warning',
        'pending': 'warning',
        'suspended': 'danger',
        'absent': 'danger',
        'inactive': 'secondary',
        'transferred': 'secondary',
        'excused': 'primary',
    }
    return mapping.get(str(value).lower(), 'secondary')


@register.filter
def field_type(field):
    return field.field.widget.__class__.__name__.lower()


@register.filter
def dict_get(mapping, key):
    if not mapping:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None
