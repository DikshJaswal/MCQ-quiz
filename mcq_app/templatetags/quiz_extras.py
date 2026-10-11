from django import template

register = template.Library()


@register.filter
def letter(index):
    """0 -> A, 1 -> B, ..."""
    try:
        return "ABCDEFGH"[int(index)]
    except (ValueError, IndexError, TypeError):
        return ""


@register.filter
def ordinal(value):
    """1 -> 1st, 2 -> 2nd, 3 -> 3rd, 4 -> 4th ..."""
    try:
        n = int(value)
    except (ValueError, TypeError):
        return value
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
