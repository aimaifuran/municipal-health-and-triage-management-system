"""Shared POST handlers for dashboard list filtering."""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views import View

from common.list_filters import sync_scope_filters_from_post


class ListFilterPostView(View):
    """Accept POST to update session filters; GET uses session only."""

    list_scope: str = ""
    q_param: str = "q"
    severity_param: str = "severity"
    page_params: tuple[str, ...] = ()

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if request.method == "POST":
            sync_scope_filters_from_post(
                request,
                self.list_scope,
                q_param=self.q_param,
                severity_param=self.severity_param,
                page_params=self.page_params,
            )
        return super().dispatch(request, *args, **kwargs)
