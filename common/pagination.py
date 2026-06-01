"""Shared pagination helpers for dashboard views."""
from __future__ import annotations

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpRequest

from common.list_filters import get_scope_filters

QUEUE_PER_PAGE = 10
PATIENTS_PER_PAGE = 10
AWAITING_PER_PAGE = 10
AUDIT_PER_PAGE = 15
LOGIN_PER_PAGE = 15
DISCHARGE_PER_PAGE = 8
READMIT_PER_PAGE = 8
DISCHARGED_TABLE_PER_PAGE = 10
READMIT_LOOKBACK_HOURS = 72
CLINICS_PER_PAGE = 10
STAFF_PER_PAGE = 12


def paginate_queryset(
    request: HttpRequest,
    queryset,
    *,
    scope: str,
    page_param: str = "page",
    per_page: int = 10,
):
    """Paginate using page number stored in session for the given list scope."""
    scope_filters = get_scope_filters(request, scope)
    page_number = scope_filters.get(page_param, 1)
    paginator = Paginator(queryset, per_page)
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)
    return page_obj
