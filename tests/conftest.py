import os

os.environ.setdefault("USE_SQLITE_DEV", "1")

import pytest
from rest_framework.test import APIClient

from accounts.models import Clinic, DoctorPatientAssignment, User, UserRole
from patients.models import Patient


@pytest.fixture
def clinic(db):
    return Clinic.objects.create(
        name="Municipal Health Center A",
        address="123 Main St",
        municipality="Cebu City",
        region="Region VII",
    )


@pytest.fixture
def doctor(db, clinic):
    user = User.objects.create_user(
        email="doctor@test.gov.ph",
        password="SecurePass123!",
        role=UserRole.DOCTOR,
        clinic=clinic,
        is_verified=True,
    )
    return user


@pytest.fixture
def nurse(db, clinic):
    return User.objects.create_user(
        email="nurse@test.gov.ph",
        password="SecurePass123!",
        role=UserRole.NURSE,
        clinic=clinic,
        is_verified=True,
    )


@pytest.fixture
def receptionist(db, clinic):
    return User.objects.create_user(
        email="reception@test.gov.ph",
        password="SecurePass123!",
        role=UserRole.RECEPTIONIST,
        clinic=clinic,
        is_verified=True,
    )


@pytest.fixture
def patient(db, clinic, receptionist):
    p = Patient.objects.create(
        patient_number="PAT-TEST-001",
        first_name="Juan",
        last_name="Dela Cruz",
        birth_date="1990-01-15",
        gender="male",
        address="Cebu",
        contact_number="+639171234567",
        emergency_contact="Maria Dela Cruz",
        clinic=clinic,
        created_by=receptionist,
    )
    return p


@pytest.fixture
def assigned_patient(db, doctor, patient):
    DoctorPatientAssignment.objects.create(doctor=doctor, patient=patient, is_active=True)
    return patient


@pytest.fixture
def api_client():
    return APIClient()
