"""DRF serializers for API v1."""
from __future__ import annotations

from rest_framework import serializers

from accounts.models import Clinic, User
from consultations.models import Consultation
from patients.models import Patient
from triage.models import TriageRecord


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "role", "clinic", "is_verified")
        read_only_fields = fields


class ClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ("id", "name", "address", "municipality", "region")


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = (
            "id",
            "patient_number",
            "first_name",
            "middle_name",
            "last_name",
            "birth_date",
            "gender",
            "address",
            "contact_number",
            "emergency_contact",
            "clinic",
            "created_at",
        )
        read_only_fields = ("id", "patient_number", "created_at")


class PatientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = (
            "first_name",
            "middle_name",
            "last_name",
            "birth_date",
            "gender",
            "address",
            "contact_number",
            "emergency_contact",
        )


class TriageRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TriageRecord
        fields = (
            "id",
            "patient",
            "blood_pressure",
            "heart_rate",
            "respiratory_rate",
            "oxygen_saturation",
            "body_temperature",
            "symptoms",
            "severity_level",
            "priority_score",
            "triage_status",
            "created_at",
        )
        read_only_fields = ("id", "severity_level", "priority_score", "created_at")


class ConsultationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = (
            "id",
            "patient",
            "doctor",
            "diagnosis",
            "treatment",
            "prescription",
            "admitted",
            "discharged",
            "consultation_notes",
            "admitted_at",
            "discharged_at",
            "created_at",
        )
        read_only_fields = ("id", "doctor", "admitted_at", "discharged_at", "created_at")


class BulkDischargeSerializer(serializers.Serializer):
    consultation_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,
    )


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, help_text="Refresh token to blacklist")


class MessageResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()


class PublicHealthStatsSerializer(serializers.Serializer):
    region = serializers.CharField()
    clinic_count = serializers.IntegerField()
    active_cases = serializers.IntegerField()
    respiratory_cases = serializers.IntegerField()
    top_symptoms = serializers.ListField(child=serializers.CharField())
    patient_name = serializers.CharField()
    patient_details = serializers.CharField()
    diagnosis = serializers.CharField(required=False)
    contact_number = serializers.CharField(required=False)
    address = serializers.CharField(required=False)
