import pytest

from accounts.models import DoctorPatientAssignment
from security.access import AccessControlService


@pytest.mark.django_db
class TestAccessControl:
    def test_nurse_can_access_clinic_patient(self, nurse, patient):
        assert AccessControlService.can_access_patient(nurse, patient) is True

    def test_doctor_requires_assignment(self, doctor, patient):
        assert AccessControlService.can_access_patient(doctor, patient) is False
        DoctorPatientAssignment.objects.create(doctor=doctor, patient=patient)
        assert AccessControlService.can_access_patient(doctor, patient) is True
