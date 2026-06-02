"""Reusable template tags for severity, priority, and critical patients."""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

SEVERITY_STYLES = {
    "critical": ("bg-red-100 text-red-800 border-red-300", "animate-pulse"),
    "moderate": ("bg-yellow-100 text-yellow-800 border-yellow-300", ""),
    "stable": ("bg-green-100 text-green-800 border-green-300", ""),
}


@register.simple_tag
def severity_badge(level: str) -> str:
    classes, extra = SEVERITY_STYLES.get(level.lower(), ("bg-gray-100 text-gray-800", ""))
    label = level.replace("_", " ").title()
    return mark_safe(
        f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border {classes} {extra}">{label}</span>'
    )


@register.simple_tag
def priority_color(score: int) -> str:
    if score >= 60:
        return "text-red-600"
    if score >= 30:
        return "text-yellow-600"
    return "text-green-600"


@register.simple_tag
def emergency_indicator(is_critical: bool) -> str:
    if not is_critical:
        return ""
    return mark_safe(
        '<span class="relative flex h-3 w-3" aria-label="Emergency">'
        '<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>'
        '<span class="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span></span>'
    )


@register.filter
def critical_patient_class(severity: str) -> str:
    if severity == "critical":
        return "border-l-4 border-red-500 bg-red-50"
    return ""


@register.filter
def queue_row_accent(severity: str) -> str:
    """Left border and background tint for active queue rows."""
    accents = {
        "critical": "border-l-[3px] border-l-red-500 bg-red-50/60",
        "moderate": "border-l-[3px] border-l-amber-400 bg-amber-50/30",
        "stable": "border-l-[3px] border-l-emerald-400",
    }
    return accents.get((severity or "").lower(), "border-l-[3px] border-l-slate-200")


@register.filter
def patient_initials(patient) -> str:
    first = (getattr(patient, "first_name", "") or "").strip()
    last = (getattr(patient, "last_name", "") or "").strip()
    if first or last:
        return f"{first[:1]}{last[:1]}".upper()
    return "PT"


@register.simple_tag(takes_context=True)
def nav_active(context, *url_names: str) -> str:
    """Return active class when current view matches any url_name."""
    request = context.get("request")
    if not request or not getattr(request, "resolver_match", None):
        return ""
    current = request.resolver_match.url_name
    if current in url_names:
        return "nav-link-active"
    if "admin-audit" in url_names and current == "admin-audit":
        return "nav-link-active"
    return ""


@register.inclusion_tag("partials/user_avatar.html")
def user_avatar(user, size: str = "md"):
    """Render profile picture or initials fallback."""
    sizes = {
        "sm": ("h-9 w-9", "text-xs"),
        "md": ("h-10 w-10", "text-sm"),
        "lg": ("h-20 w-20", "text-xl"),
        "xl": ("h-28 w-28", "text-2xl"),
    }
    dim_class, text_class = sizes.get(size, sizes["md"])
    return {
        "user": user,
        "dim_class": dim_class,
        "text_class": text_class,
        "picture_url": getattr(user, "profile_picture_url", "") or "",
        "initials": user_initials(user),
    }


@register.filter
def user_initials(user) -> str:
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    if first or last:
        return f"{first[:1]}{last[:1]}".upper() or "U"
    email = getattr(user, "email", "") or ""
    return email[:2].upper() if email else "U"


@register.filter
def role_badge_class(role: str) -> str:
    mapping = {
        "super_admin": "bg-violet-100 text-violet-800 ring-violet-200",
        "doctor": "bg-sky-100 text-sky-800 ring-sky-200",
        "nurse": "bg-teal-100 text-teal-800 ring-teal-200",
        "receptionist": "bg-amber-100 text-amber-800 ring-amber-200",
    }
    return mapping.get(role, "bg-slate-100 text-slate-700 ring-slate-200")
