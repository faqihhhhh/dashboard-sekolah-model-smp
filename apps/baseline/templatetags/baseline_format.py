from django import template

register = template.Library()


@register.filter
def trim_decimal(value):
    """Format decimals without displaying insignificant trailing zeroes."""
    if value is None or value == "":
        return ""
    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted
