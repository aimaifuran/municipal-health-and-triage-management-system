"""Server-side list filters stored in session (never in URL query strings)."""
from __future__ import annotations

from django.db.models import OuterRef, Q, QuerySet, Subquery
from django.http import HttpRequest

from triage.models import SeverityLevel, TriageRecord

VALID_SEVERITIES = frozenset(c.value for c in SeverityLevel)

SESSION_KEY = "dashboard_list_filters"


class ListScope:
    QUEUE = "queue"
    DISCHARGED = "discharged"
    AWAITING = "awaiting"
    PATIENTS = "patients"
    DISCHARGE = "discharge"
    READMIT = "readmit"
    CLINICS = "clinics"
    STAFF = "staff"
    AUDIT = "audit"
    LOGIN = "login"


def _session_store(request: HttpRequest) -> dict:
    store = request.session.get(SESSION_KEY)
    if not isinstance(store, dict):
        store = {}
    return store


def _save_store(request: HttpRequest, store: dict) -> None:
    request.session[SESSION_KEY] = store
    request.session.modified = True


def _scope_storage_key(request: HttpRequest, scope: str) -> str:
    """Isolate list filters per logged-in user (avoids bleed across roles/sessions)."""
    if request.user.is_authenticated:
        return f"user_{request.user.pk}:{scope}"
    return f"anon:{scope}"


def get_scope_filters(request: HttpRequest, scope: str) -> dict:
    """Return stored filters for a list (empty dict if none)."""
    return dict(_session_store(request).get(_scope_storage_key(request, scope), {}))


def clear_scope_filters(request: HttpRequest, scope: str) -> None:
    store = _session_store(request)
    store.pop(_scope_storage_key(request, scope), None)
    _save_store(request, store)


def sync_scope_filters_from_post(
    request: HttpRequest,
    scope: str,
    *,
    q_param: str = "q",
    severity_param: str = "severity",
    page_params: tuple[str, ...] = (),
) -> dict:
    """
    On POST, persist search/filter/page values to the session and return the scope dict.
  Read-only requests use stored session values only.
    """
    store = _session_store(request)
    storage_key = _scope_storage_key(request, scope)
    current = dict(store.get(storage_key, {}))

    if request.method == "POST":
        if request.POST.get("clear_filters"):
            current = {}
        else:
            if q_param in request.POST:
                current[q_param] = request.POST.get(q_param, "").strip()
            if severity_param in request.POST:
                raw = request.POST.get(severity_param, "").strip().lower()
                current[severity_param] = raw if raw in VALID_SEVERITIES else ""
            for page_key in page_params:
                if page_key in request.POST:
                    page_val = request.POST.get(page_key, "1")
                    if str(page_val).isdigit():
                        current[page_key] = page_val

        store[storage_key] = current
        _save_store(request, store)

    return current


def filters_for_template(
    scope_filters: dict,
    *,
    q_param: str = "q",
    severity_param: str = "severity",
) -> dict:
    severity = scope_filters.get(severity_param, "")
    if severity not in VALID_SEVERITIES:
        severity = ""
    return {
        "q": scope_filters.get(q_param, ""),
        "severity": severity,
        "q_param": q_param,
        "severity_param": severity_param,
    }


def table_filters_context(
    request: HttpRequest,
    scope: str,
    *,
    q_param: str = "q",
    severity_param: str = "severity",
    context_key: str = "table_filters",
) -> dict:
    scope_filters = get_scope_filters(request, scope)
    return {
        context_key: filters_for_template(
            scope_filters, q_param=q_param, severity_param=severity_param
        ),
        "severity_choices": SeverityLevel.choices,
        "list_scope": scope,
    }


def patient_search_q(term: str, *, prefix: str = "") -> Q:
    """
    Match patient ID or name fields.
    Supports full patient numbers (PAT-…) and multi-word names (e.g. "Jenny Aquino").
    """
    p = f"{prefix}__" if prefix else ""
    term = term.strip()
    if not term:
        return Q()

    def _field_match(fragment: str) -> Q:
        return (
            Q(**{f"{p}patient_number__icontains": fragment})
            | Q(**{f"{p}first_name__icontains": fragment})
            | Q(**{f"{p}last_name__icontains": fragment})
            | Q(**{f"{p}middle_name__icontains": fragment})
        )

    combined = _field_match(term)
    words = [w for w in term.split() if w]
    if len(words) > 1:
        multi_word = Q()
        for word in words:
            multi_word &= _field_match(word)
        combined |= multi_word
    return combined


def apply_patient_list_filters(
    qs: QuerySet, scope_filters: dict, *, q_param: str = "q"
) -> QuerySet:
    term = scope_filters.get(q_param, "").strip()
    if term:
        qs = qs.filter(patient_search_q(term))
    return qs


def apply_triage_list_filters(qs: QuerySet, scope_filters: dict) -> QuerySet:
    filters = filters_for_template(scope_filters)
    if filters["severity"]:
        qs = qs.filter(severity_level=filters["severity"])
    if filters["q"]:
        qs = qs.filter(patient_search_q(filters["q"], prefix="patient"))
    return qs


def apply_consultation_list_filters(qs: QuerySet, scope_filters: dict) -> QuerySet:
    filters = filters_for_template(scope_filters)
    if filters["severity"]:
        latest_severity = (
            TriageRecord.objects.filter(patient_id=OuterRef("patient_id"))
            .order_by("-created_at")
            .values("severity_level")[:1]
        )
        qs = qs.annotate(_list_severity=Subquery(latest_severity)).filter(
            _list_severity=filters["severity"]
        )
    if filters["q"]:
        qs = qs.filter(patient_search_q(filters["q"], prefix="patient"))
    return qs


def apply_clinic_list_filters(qs: QuerySet, scope_filters: dict) -> QuerySet:
    term = scope_filters.get("q", "").strip()
    if not term:
        return qs
    return qs.filter(
        Q(name__icontains=term)
        | Q(municipality__icontains=term)
        | Q(region__icontains=term)
        | Q(address__icontains=term)
    )


def apply_staff_list_filters(qs: QuerySet, scope_filters: dict) -> QuerySet:
    term = scope_filters.get("q", "").strip()
    if not term:
        return qs
    return qs.filter(
        Q(email__icontains=term)
        | Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(clinic__name__icontains=term)
    )


def apply_audit_list_filters(qs: QuerySet, scope_filters: dict) -> QuerySet:
    term = scope_filters.get("audit_q", "").strip()
    if not term:
        return qs
    return qs.filter(
        Q(action__icontains=term)
        | Q(object_type__icontains=term)
        | Q(object_id__icontains=term)
        | Q(user__email__icontains=term)
        | Q(ip_address__icontains=term)
        | Q(details__icontains=term)
    )


def apply_login_list_filters(qs: QuerySet, scope_filters: dict) -> QuerySet:
    term = scope_filters.get("login_q", "").strip()
    if not term:
        return qs
    return qs.filter(Q(email_attempted__icontains=term) | Q(ip_address__icontains=term))
