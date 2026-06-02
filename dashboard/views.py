"""Role-based dashboard views."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Exists, OuterRef, Prefetch, Subquery
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from accounts.forms import ClinicForm, StaffUserForm
from accounts.models import Clinic, User, UserRole
from accounts.services import STAFF_ROLES, AdminAccountService
from auditlogs.models import AuditLog, LoginAttempt
from common.list_filters import (
    ListScope,
    apply_audit_list_filters,
    apply_clinic_list_filters,
    apply_consultation_list_filters,
    apply_login_list_filters,
    apply_patient_list_filters,
    apply_staff_list_filters,
    apply_triage_list_filters,
    get_scope_filters,
    table_filters_context,
)
from common.list_views import ListFilterPostView
from common.mixins import (
    ClinicScopedMixin,
    DoctorRequiredMixin,
    NurseRequiredMixin,
    SuperAdminRequiredMixin,
)
from common.pagination import (
    AUDIT_PER_PAGE,
    AWAITING_PER_PAGE,
    CLINICS_PER_PAGE,
    DISCHARGE_PER_PAGE,
    DISCHARGED_TABLE_PER_PAGE,
    LOGIN_PER_PAGE,
    PATIENTS_PER_PAGE,
    QUEUE_PER_PAGE,
    READMIT_LOOKBACK_HOURS,
    READMIT_PER_PAGE,
    STAFF_PER_PAGE,
    paginate_queryset,
)
from consultations.ai_consultation import (
    ConsultationAIConfigurationError,
    ConsultationAIError,
    ConsultationAIRequestError,
    ConsultationAIResponseError,
    generate_consultation_suggestion,
)
from consultations.forms import ConsultationRecordForm
from consultations.models import Consultation
from consultations.services import ConsultationService
from dashboard.admin_analytics import build_admin_dashboard_analytics
from dashboard.discharge_summary import (
    build_discharge_summary_context,
    discharge_summary_filename,
    get_discharged_consultation,
    get_latest_triage,
    patient_age_years,
    render_discharge_summary_pdf,
)
from patients.forms import PatientRegistrationForm
from patients.models import Patient
from patients.services import PatientService
from security.access import AccessControlService
from triage.forms import TriageVitalsForm
from triage.models import TriageRecord
from triage.services import TriageService


def _filter_oob(request) -> bool:
    return bool(request.headers.get("HX-Request"))


def _htmx_no_cache(response):
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response["Pragma"] = "no-cache"
    return response


def _trigger_nurse_refresh(response):
    if response is not None:
        response["HX-Trigger"] = "refreshNursePanels"
    return response


def _active_queue_queryset(user, request):
    qs = TriageRecord.objects.filter(is_active=True).select_related("patient")
    if user.clinic_id and user.role != UserRole.SUPER_ADMIN:
        qs = qs.filter(patient__clinic_id=user.clinic_id)
    if user.role == UserRole.DOCTOR:
        patient_ids = AccessControlService.filter_patients_for_user(
            user, Patient.objects.all()
        ).values_list("id", flat=True)
        qs = qs.filter(patient_id__in=patient_ids)
    scope_filters = get_scope_filters(request, ListScope.QUEUE)
    qs = apply_triage_list_filters(qs, scope_filters)
    if user.role == UserRole.DOCTOR:
        open_consultation = Consultation.objects.filter(
            patient_id=OuterRef("patient_id"),
            doctor_id=user.id,
            discharged=False,
        ).order_by("-created_at")
        qs = qs.annotate(
            doctor_open_consultation_id=Subquery(open_consultation.values("id")[:1]),
            doctor_consultation_admitted=Subquery(open_consultation.values("admitted")[:1]),
        )
    elif user.role == UserRole.NURSE:
        qs = qs.annotate(
            patient_awaiting_discharge=Exists(
                Consultation.objects.filter(
                    patient_id=OuterRef("patient_id"),
                    admitted=True,
                    discharged=False,
                )
            )
        )
    return qs.order_by("-priority_score")


def _paginated_queue(request, user):
    return paginate_queryset(
        request,
        _active_queue_queryset(user, request),
        scope=ListScope.QUEUE,
        page_param="queue_page",
        per_page=QUEUE_PER_PAGE,
    )


def _doctor_discharged_consultations(user, request):
    triage_prefetch = Prefetch(
        "patient__triage_records",
        queryset=TriageRecord.objects.order_by("-created_at"),
    )
    qs = (
        AccessControlService.filter_consultations_for_user(
            user,
            Consultation.objects.filter(admitted=True, discharged=True),
        )
        .select_related("patient")
        .prefetch_related(triage_prefetch)
        .order_by("-discharged_at")
    )
    scope_filters = get_scope_filters(request, ListScope.DISCHARGED)
    return apply_consultation_list_filters(qs, scope_filters)


def _doctor_discharged_table_context(request) -> dict:
    discharged_page = paginate_queryset(
        request,
        _doctor_discharged_consultations(request.user, request),
        scope=ListScope.DISCHARGED,
        page_param="discharged_page",
        per_page=DISCHARGED_TABLE_PER_PAGE,
    )
    ctx = {
        "discharged_page": discharged_page,
        "discharged_consultations": discharged_page.object_list,
        "discharged_partial_url": reverse("dashboard:doctor-discharged-partial"),
        "page_param": "discharged_page",
        "filter_form_id": "discharged-filters-form",
    }
    ctx.update(
        table_filters_context(request, ListScope.DISCHARGED, context_key="discharged_table_filters")
    )
    ctx["table_filters"] = ctx["discharged_table_filters"]
    return ctx


def _doctor_hx_discharge_response(request, template_name: str, ctx: dict):
    response = render(request, template_name, ctx)
    if request.headers.get("HX-Request"):
        response["HX-Trigger"] = "refreshDoctorPanels"
    return response


def _awaiting_patients_queryset(user, request):
    active_triage = TriageRecord.objects.filter(
        patient_id=OuterRef("pk"),
        is_active=True,
    )
    patient_qs = AccessControlService.filter_patients_for_user(user, Patient.objects.all())
    qs = (
        patient_qs.annotate(has_active_triage=Exists(active_triage))
        .filter(has_active_triage=False)
        .order_by("-created_at")
    )
    scope_filters = get_scope_filters(request, ListScope.AWAITING)
    return apply_patient_list_filters(qs, scope_filters)


def _awaiting_table_context(request) -> dict:
    awaiting_page = paginate_queryset(
        request,
        _awaiting_patients_queryset(request.user, request),
        scope=ListScope.AWAITING,
        page_param="awaiting_page",
        per_page=AWAITING_PER_PAGE,
    )
    ctx = {
        "awaiting_page": awaiting_page,
        "awaiting_partial_url": reverse("dashboard:nurse-awaiting-partial"),
        "page_param": "awaiting_page",
        "filter_form_id": "awaiting-filters-form",
    }
    ctx.update(
        table_filters_context(request, ListScope.AWAITING, context_key="awaiting_table_filters")
    )
    return ctx


def _nurse_patient_select_context(request) -> dict:
    user = request.user
    queue_qs = _active_queue_queryset(user, request)[:100]
    awaiting_qs = _awaiting_patients_queryset(user, request)[:100]
    return {
        "queue": list(queue_qs),
        "awaiting_patients": list(awaiting_qs),
        "patient_select_partial_url": reverse("dashboard:nurse-patient-select-partial"),
    }


def _nurse_dashboard_context(request) -> dict:
    user = request.user
    queue_page = _paginated_queue(request, user)
    ctx = {
        "queue_page": queue_page,
        "queue": queue_page.object_list,
        "can_edit_triage": True,
        "patient_register_form": PatientRegistrationForm(),
        "queue_partial_url": reverse("dashboard:queue-partial"),
        "page_param": "queue_page",
        "filter_form_id": "queue-filters-form",
    }
    ctx.update(table_filters_context(request, ListScope.QUEUE, context_key="queue_table_filters"))
    ctx.update(_awaiting_table_context(request))
    ctx.update(_nurse_patient_select_context(request))
    ctx.update(_doctor_discharged_table_context(request))
    return ctx


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_template_names(self):
        role_templates = {
            UserRole.SUPER_ADMIN: "dashboard/admin.html",
            UserRole.DOCTOR: "dashboard/doctor.html",
            UserRole.NURSE: "dashboard/nurse.html",
            UserRole.RECEPTIONIST: "dashboard/receptionist.html",
        }
        role = self.request.user.role
        return [role_templates.get(role, "dashboard/home.html")]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        request = self.request
        queue_page = _paginated_queue(request, user)
        ctx["queue_page"] = queue_page
        ctx["queue"] = queue_page.object_list
        ctx.update(
            table_filters_context(request, ListScope.QUEUE, context_key="queue_table_filters")
        )
        ctx["queue_partial_url"] = reverse("dashboard:queue-partial")
        ctx["page_param"] = "queue_page"
        ctx["filter_form_id"] = "queue-filters-form"

        if user.role == UserRole.DOCTOR:
            ctx["show_doctor_consult_actions"] = True
            ctx.update(_doctor_discharge_context(request))
            ctx.update(_doctor_discharged_table_context(request))

        if user.role == UserRole.RECEPTIONIST:
            ctx.update(_receptionist_patients_context(request))

        if user.role == UserRole.NURSE:
            ctx.update(_nurse_dashboard_context(request))

        if user.role == UserRole.SUPER_ADMIN:
            analytics = build_admin_dashboard_analytics()
            ctx["stats"] = analytics["stats"]
            ctx["charts"] = analytics["charts"]
        return ctx


def _receptionist_patients_context(request) -> dict:
    patients_qs = AccessControlService.filter_patients_for_user(
        request.user, Patient.objects.all()
    ).order_by("-created_at")
    scope_filters = get_scope_filters(request, ListScope.PATIENTS)
    patients_qs = apply_patient_list_filters(patients_qs, scope_filters)
    patients_page = paginate_queryset(
        request,
        patients_qs,
        scope=ListScope.PATIENTS,
        page_param="patients_page",
        per_page=PATIENTS_PER_PAGE,
    )
    ctx = {
        "patients_page": patients_page,
        "patients": patients_page.object_list,
        "patients_partial_url": reverse("dashboard:receptionist-patients-partial"),
        "page_param": "patients_page",
        "filter_form_id": "patients-filters-form",
    }
    ctx.update(
        table_filters_context(request, ListScope.PATIENTS, context_key="patients_table_filters")
    )
    return ctx


def _doctor_discharge_context(request, results=None, readmit_results=None) -> dict:
    user = request.user
    discharge_scope = get_scope_filters(request, ListScope.DISCHARGE)
    discharge_qs = (
        AccessControlService.filter_consultations_for_user(
            user,
            Consultation.objects.filter(admitted=True, discharged=False),
        )
        .select_related("patient")
        .order_by("-admitted_at", "-created_at")
    )
    discharge_qs = apply_consultation_list_filters(discharge_qs, discharge_scope)
    discharged_since = timezone.now() - timedelta(hours=READMIT_LOOKBACK_HOURS)
    readmit_scope = get_scope_filters(request, ListScope.READMIT)
    readmit_qs = (
        AccessControlService.filter_consultations_for_user(
            user,
            Consultation.objects.filter(
                admitted=True,
                discharged=True,
                discharged_at__gte=discharged_since,
            ),
        )
        .select_related("patient")
        .order_by("-discharged_at")
    )
    readmit_qs = apply_consultation_list_filters(readmit_qs, readmit_scope)
    discharge_page = paginate_queryset(
        request,
        discharge_qs,
        scope=ListScope.DISCHARGE,
        page_param="discharge_page",
        per_page=DISCHARGE_PER_PAGE,
    )
    readmit_page = paginate_queryset(
        request,
        readmit_qs,
        scope=ListScope.READMIT,
        page_param="readmit_page",
        per_page=READMIT_PER_PAGE,
    )
    ctx = {
        "discharge_page": discharge_page,
        "admitted_consultations": discharge_page.object_list,
        "readmit_page": readmit_page,
        "recently_discharged": readmit_page.object_list,
        "readmit_lookback_hours": READMIT_LOOKBACK_HOURS,
        "discharge_panel_partial_url": reverse("dashboard:doctor-discharge-panel-partial"),
        "page_param": "discharge_page",
        "filter_form_id": "discharge-filters-form",
    }
    if results is not None:
        ctx["results"] = results
    if readmit_results is not None:
        ctx["readmit_results"] = readmit_results
    ctx.update(
        table_filters_context(request, ListScope.DISCHARGE, context_key="discharge_table_filters")
    )
    ctx["table_filters"] = ctx["discharge_table_filters"]
    return ctx


class UnauthorizedView(TemplateView):
    template_name = "errors/403.html"


class DoctorBulkDischargeView(DoctorRequiredMixin, View):
    def post(self, request):
        ids = request.POST.getlist("consultation_ids")
        if not ids:
            results = {
                "success": [],
                "failed": [],
                "notice": "Select at least one patient to discharge.",
            }
        else:
            results = ConsultationService.bulk_discharge(ids, request.user, request)

        if request.headers.get("HX-Request"):
            ctx = _doctor_discharge_context(request, results=results)
            return _doctor_hx_discharge_response(
                request,
                "dashboard/partials/bulk_discharge_panel.html",
                ctx,
            )

        home = DashboardHomeView()
        home.setup(request)
        ctx = home.get_context_data()
        ctx["results"] = results
        return render(request, "dashboard/doctor.html", ctx)


class DoctorBulkReadmitView(DoctorRequiredMixin, View):
    """Restore recently discharged patients to the active discharge list."""

    def post(self, request):
        ids = request.POST.getlist("readmit_consultation_ids")
        if not ids:
            readmit_results = {
                "success": [],
                "failed": [],
                "notice": "Select at least one discharged patient to restore.",
            }
        else:
            readmit_results = ConsultationService.bulk_readmit(ids, request.user, request)

        if request.headers.get("HX-Request"):
            ctx = _doctor_discharge_context(request, readmit_results=readmit_results)
            return _doctor_hx_discharge_response(
                request,
                "dashboard/partials/bulk_discharge_panel.html",
                ctx,
            )

        home = DashboardHomeView()
        home.setup(request)
        ctx = home.get_context_data()
        ctx["readmit_results"] = readmit_results
        return render(request, "dashboard/doctor.html", ctx)


class QueuePartialView(LoginRequiredMixin, ClinicScopedMixin, ListFilterPostView):
    """HTMX partial: POST applies filters (session); GET polls with stored filters."""

    list_scope = ListScope.QUEUE
    page_params = ("queue_page",)

    def get(self, request):
        return self._render(request)

    def post(self, request):
        return self._render(request)

    def _render(self, request):
        queue_page = _paginated_queue(request, request.user)
        ctx = {
            "queue_page": queue_page,
            "queue": queue_page.object_list,
            "can_edit_triage": request.user.role == UserRole.NURSE,
            "queue_partial_url": reverse("dashboard:queue-partial"),
            "page_param": "queue_page",
            "filter_form_id": "queue-filters-form",
        }
        ctx.update(
            table_filters_context(request, ListScope.QUEUE, context_key="queue_table_filters")
        )
        ctx["queue_hx_target"] = (
            "#nurse-queue-panel" if request.user.role == UserRole.NURSE else "#queue-container"
        )
        ctx["queue_partial_url"] = reverse("dashboard:queue-partial")
        ctx["filter_form_id"] = "queue-filters-form"
        ctx["page_param"] = "queue_page"
        ctx["show_doctor_consult_actions"] = request.user.role == UserRole.DOCTOR
        ctx["severity_before_actions"] = request.user.role == UserRole.DOCTOR
        ctx["filter_oob"] = _filter_oob(request)
        return _htmx_no_cache(render(request, "dashboard/partials/queue_panel.html", ctx))


class NursePatientSelectPartialView(NurseRequiredMixin, View):
    """HTMX partial: patient picker for vitals (polls for doctor queue changes)."""

    def get(self, request):
        return self._render(request)

    def _render(self, request):
        return _htmx_no_cache(
            render(
                request,
                "dashboard/partials/nurse_patient_select.html",
                _nurse_patient_select_context(request),
            )
        )


class DoctorQueueConsultationFormView(DoctorRequiredMixin, View):
    """HTMX modal: record consultation details for a queued patient."""

    def get(self, request):
        patient = get_object_or_404(Patient, pk=request.GET.get("patient"))
        AccessControlService.assert_patient_access(request.user, patient, request)
        triage = (
            TriageRecord.objects.filter(patient=patient, is_active=True)
            .select_related("nurse")
            .first()
        )
        consultation = ConsultationService.get_open_consultation(patient, request.user)
        form = (
            ConsultationRecordForm(instance=consultation)
            if consultation
            else ConsultationRecordForm()
        )
        return render(
            request,
            "dashboard/partials/doctor_queue_consultation_modal.html",
            {
                "patient": patient,
                "triage": triage,
                "consultation": consultation,
                "form": form,
            },
        )


class DoctorQueueConsultationSubmitView(DoctorRequiredMixin, View):
    """Save consultation details and optionally move patient to awaiting discharge."""

    def post(self, request):
        patient = get_object_or_404(Patient, pk=request.POST.get("patient_id"))
        AccessControlService.assert_patient_access(request.user, patient, request)
        action = request.POST.get("action", "save")
        form = ConsultationRecordForm(request.POST)
        triage = (
            TriageRecord.objects.filter(patient=patient, is_active=True)
            .select_related("nurse")
            .first()
        )

        if not form.is_valid():
            consultation = ConsultationService.get_open_consultation(patient, request.user)
            response = render(
                request,
                "dashboard/partials/doctor_queue_consultation_modal.html",
                {
                    "patient": patient,
                    "triage": triage,
                    "consultation": consultation,
                    "form": form,
                },
                status=400,
            )
            if request.headers.get("HX-Request"):
                response["HX-Retarget"] = "#doctor-consultation-modal"
                response["HX-Reswap"] = "innerHTML"
            return response

        data = form.cleaned_data
        if action == "admit":
            existing = ConsultationService.get_open_consultation(patient, request.user)
            already_admitted = bool(existing and existing.admitted)
            consultation = ConsultationService.save_and_admit(
                patient=patient,
                doctor=request.user,
                validated_data=data,
                request=request,
            )
            message = (
                f"Consultation updated for {patient.patient_number} (already awaiting discharge)."
                if already_admitted
                else f"{patient.patient_number} is now in Awaiting discharge."
            )
        else:
            consultation = ConsultationService.upsert_consultation(
                patient=patient,
                doctor=request.user,
                validated_data=data,
                request=request,
            )
            message = f"Consultation saved for {patient.patient_number}."

        if request.headers.get("HX-Request"):
            ctx = {
                "message": message,
                "patient": patient,
                "consultation": consultation,
                "queue_page": _paginated_queue(request, request.user),
                "can_edit_triage": False,
                "show_doctor_consult_actions": True,
                "queue_partial_url": reverse("dashboard:queue-partial"),
                "page_param": "queue_page",
                "filter_form_id": "queue-filters-form",
                "queue_hx_target": "#queue-container",
            }
            ctx.update(_doctor_discharge_context(request))
            ctx.update(
                table_filters_context(request, ListScope.QUEUE, context_key="queue_table_filters")
            )
            response = render(
                request,
                "dashboard/partials/doctor_consultation_success.html",
                ctx,
            )
            response["HX-Trigger"] = "refreshDoctorPanels"
            return response

        return redirect("dashboard:home")


@method_decorator(require_POST, name="dispatch")
class DoctorQueueConsultationAIView(DoctorRequiredMixin, View):
    """Generate draft consultation fields via OpenAI for doctor review."""

    def post(self, request):
        patient = get_object_or_404(Patient, pk=request.POST.get("patient_id"))
        AccessControlService.assert_patient_access(request.user, patient, request)
        triage = (
            TriageRecord.objects.filter(patient=patient, is_active=True)
            .select_related("nurse", "patient", "patient__clinic")
            .first()
        )
        consultation = ConsultationService.get_open_consultation(patient, request.user)
        try:
            suggestion = generate_consultation_suggestion(patient, triage, consultation)
        except ConsultationAIConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=503)
        except ConsultationAIRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=502)
        except ConsultationAIResponseError as exc:
            return JsonResponse({"error": str(exc)}, status=502)
        except ConsultationAIError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        return JsonResponse(
            {
                **suggestion.as_dict(),
                "disclaimer": (
                    "AI-generated draft for physician review only. Verify examination findings, "
                    "update as needed, and accept clinical responsibility before saving."
                ),
            }
        )


class DoctorDischargedPartialView(LoginRequiredMixin, ListFilterPostView):
    """HTMX partial for the doctor's discharged patients table."""

    list_scope = ListScope.DISCHARGED
    page_params = ("discharged_page",)

    def get(self, request):
        if request.user.role not in (UserRole.DOCTOR, UserRole.NURSE):
            return redirect("dashboard:unauthorized")
        return self._render(request)

    def post(self, request):
        if request.user.role not in (UserRole.DOCTOR, UserRole.NURSE):
            return redirect("dashboard:unauthorized")
        return self._render(request)

    def _render(self, request):
        ctx = _doctor_discharged_table_context(request)
        ctx["filter_oob"] = _filter_oob(request)
        return render(request, "dashboard/partials/discharged_patients_table.html", ctx)


class NurseAwaitingPartialView(NurseRequiredMixin, ListFilterPostView):
    list_scope = ListScope.AWAITING
    page_params = ("awaiting_page",)

    def get(self, request):
        return self._render(request)

    def post(self, request):
        return self._render(request)

    def _render(self, request):
        ctx = _awaiting_table_context(request)
        ctx["filter_oob"] = _filter_oob(request)
        return _htmx_no_cache(
            render(request, "dashboard/partials/awaiting_patients_table.html", ctx)
        )


class ReceptionistPatientsPartialView(LoginRequiredMixin, ListFilterPostView):
    list_scope = ListScope.PATIENTS
    page_params = ("patients_page",)

    def get(self, request):
        if request.user.role != UserRole.RECEPTIONIST:
            return redirect("dashboard:unauthorized")
        return self._render(request)

    def post(self, request):
        if request.user.role != UserRole.RECEPTIONIST:
            return redirect("dashboard:unauthorized")
        return self._render(request)

    def _render(self, request):
        ctx = _receptionist_patients_context(request)
        ctx["filter_oob"] = _filter_oob(request)
        return render(request, "dashboard/partials/receptionist_patients_table.html", ctx)


class DoctorDischargePanelPartialView(DoctorRequiredMixin, ListFilterPostView):
    list_scope = ListScope.DISCHARGE
    page_params = ("discharge_page", "readmit_page")

    def get(self, request):
        return self._render(request)

    def post(self, request):
        return self._render(request)

    def _render(self, request):
        ctx = _doctor_discharge_context(request)
        return render(request, "dashboard/partials/bulk_discharge_panel.html", ctx)


class DoctorDischargedPatientDetailView(LoginRequiredMixin, View):
    """HTMX modal with full details for a discharged consultation."""

    def get(self, request, pk):
        if request.user.role not in (UserRole.DOCTOR, UserRole.NURSE):
            return redirect("dashboard:unauthorized")
        consultation = get_discharged_consultation(request.user, pk, request)
        return render(
            request,
            "dashboard/partials/discharged_patient_detail_modal.html",
            {
                "consultation": consultation,
                "patient": consultation.patient,
                "triage": get_latest_triage(consultation),
            },
        )


class DoctorDischargedPatientSummaryDownloadView(LoginRequiredMixin, View):
    """PDF discharge summary for the patient (download)."""

    def get(self, request, pk):
        if request.user.role not in (UserRole.DOCTOR, UserRole.NURSE):
            return redirect("dashboard:unauthorized")
        consultation = get_discharged_consultation(request.user, pk, request)
        summary = build_discharge_summary_context(consultation)
        response = HttpResponse(
            render_discharge_summary_pdf(summary), content_type="application/pdf"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{discharge_summary_filename(summary)}"'
        )
        return response


class DoctorDischargedPatientSummaryPrintView(LoginRequiredMixin, View):
    """Print-friendly discharge summary (opens browser print dialog)."""

    def get(self, request, pk):
        if request.user.role not in (UserRole.DOCTOR, UserRole.NURSE):
            return redirect("dashboard:unauthorized")
        consultation = get_discharged_consultation(request.user, pk, request)
        summary = build_discharge_summary_context(consultation)
        visit_date = consultation.discharged_at or consultation.admitted_at
        on_date = timezone.localtime(visit_date).date() if visit_date else None
        return render(
            request,
            "dashboard/discharge_summary_print.html",
            {
                "consultation": summary.consultation,
                "patient": summary.patient,
                "triage": summary.triage,
                "document_ref": summary.document_ref,
                "generated_at": summary.generated_at,
                "patient_age": patient_age_years(summary.patient.birth_date, on_date),
            },
        )


def _admin_clinics_context(request) -> dict:
    edit_clinic = None
    clinic_form = ClinicForm()
    clinic_id = request.GET.get("edit_clinic")
    if clinic_id:
        edit_clinic = get_object_or_404(Clinic, pk=clinic_id)
        clinic_form = ClinicForm(instance=edit_clinic)

    scope_filters = get_scope_filters(request, ListScope.CLINICS)
    clinics_qs = apply_clinic_list_filters(
        Clinic.objects.annotate(staff_count=Count("staff")).order_by("name"),
        scope_filters,
    )
    clinics_page = paginate_queryset(
        request,
        clinics_qs,
        scope=ListScope.CLINICS,
        page_param="page",
        per_page=CLINICS_PER_PAGE,
    )
    ctx = {
        "clinics_page": clinics_page,
        "clinics": clinics_page.object_list,
        "clinic_form": clinic_form,
        "edit_clinic": edit_clinic,
        "clinics_partial_url": reverse("dashboard:admin-clinics-partial"),
        "page_param": "page",
        "filter_form_id": "clinics-filters-form",
    }
    ctx.update(table_filters_context(request, ListScope.CLINICS, context_key="table_filters"))
    return ctx


def _admin_staff_context(request) -> dict:
    role_filter = request.GET.get("role", "all")
    staff_qs = (
        User.objects.filter(role__in=STAFF_ROLES).select_related("clinic").order_by("role", "email")
    )
    if role_filter in STAFF_ROLES:
        staff_qs = staff_qs.filter(role=role_filter)
    scope_filters = get_scope_filters(request, ListScope.STAFF)
    staff_qs = apply_staff_list_filters(staff_qs, scope_filters)

    edit_staff = None
    staff_form = StaffUserForm()
    staff_id = request.GET.get("edit_staff")
    if staff_id:
        edit_staff = get_object_or_404(User, pk=staff_id, role__in=STAFF_ROLES)
        staff_form = StaffUserForm(instance=edit_staff)

    staff_page = paginate_queryset(
        request,
        staff_qs,
        scope=ListScope.STAFF,
        page_param="page",
        per_page=STAFF_PER_PAGE,
    )
    ctx = {
        "staff_page": staff_page,
        "staff_users": staff_page.object_list,
        "staff_form": staff_form,
        "edit_staff": edit_staff,
        "role_filter": role_filter,
        "staff_roles": [
            ("all", "All staff"),
            (UserRole.DOCTOR, "Doctors"),
            (UserRole.NURSE, "Nurses"),
            (UserRole.RECEPTIONIST, "Receptionists"),
        ],
        "staff_partial_url": reverse("dashboard:admin-staff-partial"),
        "page_param": "page",
        "filter_form_id": "staff-filters-form",
    }
    ctx.update(table_filters_context(request, ListScope.STAFF, context_key="table_filters"))
    return ctx


class AdminClinicsView(SuperAdminRequiredMixin, TemplateView):
    template_name = "dashboard/admin_clinics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_admin_clinics_context(self.request))
        return ctx


class AdminStaffView(SuperAdminRequiredMixin, TemplateView):
    template_name = "dashboard/admin_staff.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_admin_staff_context(self.request))
        return ctx


class AdminClinicSaveView(SuperAdminRequiredMixin, View):
    def post(self, request):
        clinic_id = request.POST.get("clinic_id")
        instance = get_object_or_404(Clinic, pk=clinic_id) if clinic_id else None
        form = ClinicForm(request.POST, instance=instance)
        if not form.is_valid():
            ctx = _admin_clinics_context(request)
            ctx["clinic_form"] = form
            ctx["edit_clinic"] = instance
            return render(request, "dashboard/admin_clinics.html", ctx, status=400)

        try:
            if instance:
                AdminAccountService.update_clinic(
                    clinic=instance,
                    actor=request.user,
                    validated_data=form.cleaned_data,
                    request=request,
                )
                messages.success(request, f"Clinic “{instance.name}” updated.")
            else:
                clinic = AdminAccountService.create_clinic(
                    actor=request.user,
                    validated_data=form.cleaned_data,
                    request=request,
                )
                messages.success(request, f"Clinic “{clinic.name}” created.")
        except ValueError as exc:
            form.add_error(None, str(exc))
            ctx = _admin_clinics_context(request)
            ctx["clinic_form"] = form
            ctx["edit_clinic"] = instance
            return render(request, "dashboard/admin_clinics.html", ctx, status=400)

        return redirect("dashboard:admin-clinics")


class AdminStaffSaveView(SuperAdminRequiredMixin, View):
    def post(self, request):
        staff_id = request.POST.get("staff_id")
        instance = get_object_or_404(User, pk=staff_id, role__in=STAFF_ROLES) if staff_id else None
        form = StaffUserForm(request.POST, instance=instance)
        if not form.is_valid():
            ctx = _admin_staff_context(request)
            ctx["staff_form"] = form
            ctx["edit_staff"] = instance
            return render(request, "dashboard/admin_staff.html", ctx, status=400)

        data = form.cleaned_data.copy()
        if not data.get("password"):
            data.pop("password", None)

        try:
            if instance:
                AdminAccountService.update_staff_user(
                    staff_user=instance,
                    actor=request.user,
                    validated_data=data,
                    request=request,
                )
                messages.success(request, f"Staff account {instance.email} updated.")
            else:
                user = AdminAccountService.create_staff_user(
                    actor=request.user,
                    validated_data=data,
                    request=request,
                )
                messages.success(request, f"Staff account {user.email} created.")
        except ValueError as exc:
            form.add_error(None, str(exc))
            ctx = _admin_staff_context(request)
            ctx["staff_form"] = form
            ctx["edit_staff"] = instance
            return render(request, "dashboard/admin_staff.html", ctx, status=400)

        role = request.POST.get("role_filter") or request.GET.get("role", "all")
        base = reverse("dashboard:admin-staff")
        if role in STAFF_ROLES:
            return redirect(f"{base}?role={role}")
        return redirect(base)


def _admin_audit_context(request) -> dict:
    audit_scope = get_scope_filters(request, ListScope.AUDIT)
    audit_qs = apply_audit_list_filters(
        AuditLog.objects.select_related("user").order_by("-timestamp"),
        audit_scope,
    )
    audit_page = paginate_queryset(
        request,
        audit_qs,
        scope=ListScope.AUDIT,
        page_param="audit_page",
        per_page=AUDIT_PER_PAGE,
    )
    login_scope = get_scope_filters(request, ListScope.LOGIN)
    login_qs = apply_login_list_filters(
        LoginAttempt.objects.all().order_by("-timestamp"),
        login_scope,
    )
    login_page = paginate_queryset(
        request,
        login_qs,
        scope=ListScope.LOGIN,
        page_param="login_page",
        per_page=LOGIN_PER_PAGE,
    )
    ctx = {
        "audit_page": audit_page,
        "audit_logs": audit_page.object_list,
        "login_page": login_page,
        "login_attempts": login_page.object_list,
        "audit_partial_url": reverse("dashboard:admin-audit-partial"),
        "login_partial_url": reverse("dashboard:admin-login-partial"),
        "audit_page_param": "audit_page",
        "login_page_param": "login_page",
        "audit_filter_form_id": "audit-filters-form",
        "login_filter_form_id": "login-filters-form",
    }
    ctx.update(
        table_filters_context(
            request,
            ListScope.AUDIT,
            q_param="audit_q",
            severity_param="audit_severity",
            context_key="audit_table_filters",
        )
    )
    ctx.update(
        table_filters_context(
            request,
            ListScope.LOGIN,
            q_param="login_q",
            severity_param="login_severity",
            context_key="login_table_filters",
        )
    )
    return ctx


class AdminAuditLogView(SuperAdminRequiredMixin, TemplateView):
    template_name = "dashboard/admin_audit.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_admin_audit_context(self.request))
        return ctx


class AdminClinicsTablePartialView(SuperAdminRequiredMixin, ListFilterPostView):
    list_scope = ListScope.CLINICS
    page_params = ("page",)

    def get(self, request):
        return self._render(request)

    def post(self, request):
        return self._render(request)

    def _render(self, request):
        ctx = _admin_clinics_context(request)
        ctx["filter_oob"] = _filter_oob(request)
        return render(request, "dashboard/partials/admin_clinics_table.html", ctx)


class AdminStaffTablePartialView(SuperAdminRequiredMixin, ListFilterPostView):
    list_scope = ListScope.STAFF
    page_params = ("page",)

    def get(self, request):
        return self._render(request)

    def post(self, request):
        return self._render(request)

    def _render(self, request):
        ctx = _admin_staff_context(request)
        ctx["filter_oob"] = _filter_oob(request)
        return render(request, "dashboard/partials/admin_staff_table.html", ctx)


class AdminAuditTablePartialView(SuperAdminRequiredMixin, ListFilterPostView):
    list_scope = ListScope.AUDIT
    q_param = "audit_q"
    severity_param = "audit_severity"
    page_params = ("audit_page",)

    def get(self, request):
        return self._render(request)

    def post(self, request):
        return self._render(request)

    def _render(self, request):
        ctx = _admin_audit_context(request)
        ctx["filter_oob"] = _filter_oob(request)
        return render(request, "dashboard/partials/admin_audit_table.html", ctx)


class AdminLoginTablePartialView(SuperAdminRequiredMixin, ListFilterPostView):
    list_scope = ListScope.LOGIN
    q_param = "login_q"
    severity_param = "login_severity"
    page_params = ("login_page",)

    def get(self, request):
        return self._render(request)

    def post(self, request):
        return self._render(request)

    def _render(self, request):
        ctx = _admin_audit_context(request)
        ctx["filter_oob"] = _filter_oob(request)
        return render(request, "dashboard/partials/admin_login_table.html", ctx)


def _triage_form_initial(record: TriageRecord | None) -> dict:
    if not record:
        return {}
    return {
        "blood_pressure": record.blood_pressure,
        "heart_rate": record.heart_rate,
        "respiratory_rate": record.respiratory_rate,
        "oxygen_saturation": record.oxygen_saturation,
        "body_temperature": record.body_temperature,
        "symptoms": record.symptoms,
    }


class TriageSeverityDocsView(LoginRequiredMixin, TemplateView):
    """Reference documentation for automatic severity evaluation."""

    template_name = "dashboard/triage_severity_docs.html"


class NurseTriageFormPartialView(NurseRequiredMixin, View):
    """HTMX: load vitals form for a selected patient (new or update)."""

    def get(self, request):
        patient = get_object_or_404(Patient, pk=request.GET.get("patient"))
        AccessControlService.assert_patient_access(request.user, patient, request)
        record = TriageRecord.objects.filter(patient=patient, is_active=True).first()
        form = TriageVitalsForm(initial=_triage_form_initial(record))
        return render(
            request,
            "dashboard/partials/triage_form.html",
            {
                "form": form,
                "patient": patient,
                "triage_record": record,
            },
        )


class NurseTriageSubmitView(NurseRequiredMixin, View):
    """Create or update triage vitals for a patient."""

    def post(self, request):
        patient = get_object_or_404(Patient, pk=request.POST.get("patient_id"))
        AccessControlService.assert_patient_access(request.user, patient, request)
        record = TriageRecord.objects.filter(patient=patient, is_active=True).first()
        form = TriageVitalsForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "dashboard/partials/triage_form.html",
                {
                    "form": form,
                    "patient": patient,
                    "triage_record": record,
                },
                status=400,
            )

        data = form.cleaned_data
        if record:
            record = TriageService.update_vitals(record, data, request.user, request)
            action = "updated"
        else:
            record = TriageService.create_triage(
                patient=patient,
                nurse=request.user,
                validated_data=data,
                request=request,
            )
            action = "recorded"

        messages.success(
            request,
            f"Vitals {action} for {patient.patient_number}. "
            f"Priority: {record.priority_score} ({record.get_severity_level_display()}).",
        )

        if request.headers.get("HX-Request"):
            ctx = _nurse_dashboard_context(request)
            ctx["record"] = record
            return _trigger_nurse_refresh(
                render(request, "dashboard/partials/nurse_triage_success.html", ctx)
            )

        return render(request, "dashboard/nurse.html", _nurse_dashboard_context(request))


class NursePatientRegisterView(NurseRequiredMixin, View):
    """Register a new patient from the nurse dashboard."""

    def post(self, request):
        form = PatientRegistrationForm(request.POST)
        if not form.is_valid():
            ctx = _nurse_dashboard_context(request)
            ctx["patient_register_form"] = form
            return render(
                request,
                "dashboard/partials/patient_register_panel.html",
                ctx,
                status=400,
            )

        try:
            patient = PatientService.create_patient(
                user=request.user,
                validated_data=form.cleaned_data,
                request=request,
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
            ctx = _nurse_dashboard_context(request)
            ctx["patient_register_form"] = form
            return render(
                request,
                "dashboard/partials/patient_register_panel.html",
                ctx,
                status=400,
            )

        messages.success(
            request,
            f"Patient {patient.patient_number} ({patient.full_name}) registered.",
        )

        if request.headers.get("HX-Request"):
            ctx = _nurse_dashboard_context(request)
            ctx["new_patient"] = patient
            ctx["triage_form"] = TriageVitalsForm()
            return _trigger_nurse_refresh(
                render(request, "dashboard/partials/patient_register_success.html", ctx)
            )

        return render(request, "dashboard/nurse.html", _nurse_dashboard_context(request))
