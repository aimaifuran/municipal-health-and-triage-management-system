"""API v1 viewsets and views."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserRole
from analytics.services import AnalyticsService
from api.v1.serializers import (
    BulkDischargeSerializer,
    ConsultationSerializer,
    LogoutSerializer,
    MessageResponseSerializer,
    PatientCreateSerializer,
    PatientSerializer,
    PublicHealthStatsSerializer,
    RegionalHealthStatsSerializer,
    TriageRecordSerializer,
    UserProfileSerializer,
)
from auditlogs.models import AuditAction
from auditlogs.services import AuditService
from consultations.models import Consultation
from consultations.services import ConsultationService
from patients.models import Patient
from patients.services import PatientService
from security.access import AccessControlService
from security.permissions import (
    DenyConsultationForReceptionist,
    IsClinicalStaff,
    IsDoctor,
    IsNurse,
    IsReceptionist,
    IsSuperAdmin,
)
from triage.models import TriageRecord
from triage.services import TriageService


class PublicApiRateThrottle(AnonRateThrottle):
    scope = "public"


@extend_schema(tags=["Authentication"])
class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema(
    tags=["Authentication"], request=LogoutSerializer, responses=MessageResponseSerializer
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                token = RefreshToken(refresh)
                token.blacklist()
            except TokenError:
                pass
        AuditService.log(
            action=AuditAction.LOGOUT,
            object_type="User",
            object_id=str(request.user.id),
            user=request.user,
            request=request,
        )
        return Response({"success": True, "message": "Logged out successfully."})


@extend_schema_view(
    list=extend_schema(tags=["Patients"]),
    retrieve=extend_schema(tags=["Patients"]),
    create=extend_schema(tags=["Patients"]),
    update=extend_schema(tags=["Patients"]),
    partial_update=extend_schema(tags=["Patients"]),
    destroy=extend_schema(tags=["Patients"]),
)
class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.none()
    serializer_class = PatientSerializer
    filterset_fields = ["gender", "clinic"]
    search_fields = ["first_name", "last_name", "patient_number"]
    ordering_fields = ["created_at", "last_name"]
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update"):
            return [IsAuthenticated(), (IsReceptionist | IsNurse | IsSuperAdmin)()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Patient.objects.none()
        qs = Patient.objects.select_related("clinic", "created_by")
        return AccessControlService.filter_patients_for_user(self.request.user, qs)

    def get_serializer_class(self):
        if self.action == "create":
            return PatientCreateSerializer
        return PatientSerializer

    def perform_create(self, serializer):
        try:
            patient = PatientService.create_patient(
                user=self.request.user,
                validated_data={**serializer.validated_data, "clinic": self.request.user.clinic},
                request=self.request,
            )
            serializer.instance = patient
        except ValueError as e:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(str(e)) from e

    def retrieve(self, request, *args, **kwargs):
        patient = self.get_object()
        AccessControlService.assert_patient_access(request.user, patient, request)
        return super().retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        patient = self.get_object()
        AccessControlService.assert_patient_access(request.user, patient, request)
        PatientService.archive_patient(patient, request.user, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Patients"])
class PatientQueueView(generics.ListAPIView):
    queryset = Patient.objects.none()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated, IsClinicalStaff]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Patient.objects.none()
        qs = (
            Patient.objects.filter(
                triage_records__is_active=True,
                triage_records__triage_status__in=["waiting", "escalated", "in_progress"],
            )
            .select_related("clinic")
            .distinct()
        )
        return AccessControlService.filter_patients_for_user(self.request.user, qs)


@extend_schema_view(
    list=extend_schema(tags=["Triage"]),
    retrieve=extend_schema(tags=["Triage"]),
    create=extend_schema(tags=["Triage"]),
    update=extend_schema(tags=["Triage"]),
    partial_update=extend_schema(tags=["Triage"]),
)
class TriageViewSet(viewsets.ModelViewSet):
    queryset = TriageRecord.objects.none()
    serializer_class = TriageRecordSerializer
    permission_classes = [IsAuthenticated, IsNurse | IsSuperAdmin]
    filterset_fields = ["severity_level", "triage_status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TriageRecord.objects.none()
        qs = TriageRecord.objects.select_related("patient", "nurse").filter(is_active=True)
        user = self.request.user
        if user.is_authenticated and user.role != UserRole.SUPER_ADMIN:
            qs = qs.filter(patient__clinic_id=user.clinic_id)
        return qs

    def perform_create(self, serializer):
        patient = get_object_or_404(Patient, pk=self.request.data.get("patient"))
        AccessControlService.assert_patient_access(self.request.user, patient, self.request)
        record = TriageService.create_triage(
            patient=patient,
            nurse=self.request.user,
            validated_data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = record

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()
        vitals = {
            k: v
            for k, v in request.data.items()
            if k
            in (
                "blood_pressure",
                "heart_rate",
                "respiratory_rate",
                "oxygen_saturation",
                "body_temperature",
                "symptoms",
            )
        }
        if "severity_level" in request.data:
            record.severity_level = request.data["severity_level"]
            record.save(update_fields=["severity_level", "updated_at"])
        if vitals:
            record = TriageService.update_vitals(record, vitals, request.user, request)
        serializer = self.get_serializer(record)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=["Consultations"]),
    retrieve=extend_schema(tags=["Consultations"]),
    create=extend_schema(tags=["Consultations"]),
    update=extend_schema(tags=["Consultations"]),
    partial_update=extend_schema(tags=["Consultations"]),
)
class ConsultationViewSet(viewsets.ModelViewSet):
    queryset = Consultation.objects.none()
    serializer_class = ConsultationSerializer
    permission_classes = [IsAuthenticated, IsDoctor, DenyConsultationForReceptionist]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Consultation.objects.none()
        qs = Consultation.objects.select_related("patient", "doctor")
        return AccessControlService.filter_consultations_for_user(self.request.user, qs)

    def perform_create(self, serializer):
        patient = serializer.validated_data["patient"]
        AccessControlService.assert_patient_access(self.request.user, patient, self.request)
        consultation = ConsultationService.create_consultation(
            patient=patient,
            doctor=self.request.user,
            validated_data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = consultation


@extend_schema(tags=["Consultations"], responses=ConsultationSerializer)
class AdmitPatientView(APIView):
    permission_classes = [IsAuthenticated, IsDoctor]
    serializer_class = ConsultationSerializer

    def post(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk, doctor=request.user)
        ConsultationService.admit_patient(consultation, request.user, request)
        return Response(ConsultationSerializer(consultation).data)


@extend_schema(tags=["Consultations"], responses=ConsultationSerializer)
class DischargePatientView(APIView):
    permission_classes = [IsAuthenticated, IsDoctor]
    serializer_class = ConsultationSerializer

    def post(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk, doctor=request.user)
        ConsultationService.discharge_patient(consultation, request.user, request)
        return Response(ConsultationSerializer(consultation).data)


@extend_schema(tags=["Consultations"], request=BulkDischargeSerializer)
class BulkDischargeView(APIView):
    permission_classes = [IsAuthenticated, IsDoctor]
    serializer_class = BulkDischargeSerializer

    def post(self, request):
        serializer = BulkDischargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = ConsultationService.bulk_discharge(
            serializer.validated_data["consultation_ids"],
            request.user,
            request,
        )
        return Response(
            {
                "success": True,
                "message": f"Bulk discharge completed: {len(results['success'])} succeeded.",
                "results": results,
            }
        )


@extend_schema(tags=["Analytics"])
class ClinicStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Clinic statistics JSON object")})
    def get(self, request):
        clinic_id = request.query_params.get("clinic_id") or request.user.clinic_id
        data = AnalyticsService.clinic_statistics(clinic_id)
        return Response(data)


@extend_schema(tags=["Analytics"])
class RegionalStatisticsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: OpenApiResponse(description="Regional statistics JSON object")})
    def get(self, request):
        region = request.query_params.get("region", "")
        return Response(AnalyticsService.regional_statistics(region))


@extend_schema(tags=["Analytics"], responses=RegionalHealthStatsSerializer)
class RegionalHealthStatsView(APIView):
    """
    Authenticated regional report — masked vs unmasked by role.

    - Doctor / Nurse / Admin / Receptionist → clinical_full (real PHI sample).
    - API Consumer → public_masked (same as /public/health-stats/).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        region = request.query_params.get("region", "")
        masked = request.user.role == UserRole.API_CONSUMER
        data = AnalyticsService.regional_health_report(region, masked=masked)
        return Response(data)


@extend_schema(tags=["Public"], responses=PublicHealthStatsSerializer)
class PublicMaskedStatsView(APIView):
    """Unauthenticated public API — masked data only."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicApiRateThrottle]

    def get(self, request):
        region = request.query_params.get("region", "")
        data = AnalyticsService.public_masked_stats(region)
        AuditService.log(
            action=AuditAction.API_ACCESS,
            object_type="PublicAPI",
            object_id="masked_stats",
            request=request,
            details={"region": region},
        )
        return Response(data)
