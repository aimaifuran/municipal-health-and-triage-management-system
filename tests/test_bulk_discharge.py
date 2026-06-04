import pytest

from auditlogs.models import AuditLog
from consultations.models import Consultation
from consultations.services import ConsultationService


@pytest.mark.django_db
class TestBulkDischarge:
    def test_bulk_discharge_success(self, doctor, assigned_patient):
        c1 = Consultation.objects.create(
            patient=assigned_patient,
            doctor=doctor,
            diagnosis="Flu",
            treatment="Rest",
            admitted=True,
        )
        results = ConsultationService.bulk_discharge([c1.id], doctor)
        assert len(results["success"]) == 1
        c1.refresh_from_db()
        assert c1.discharged is True

    def test_bulk_discharge_multiple_success(self, doctor, assigned_patient):
        c1 = Consultation.objects.create(
            patient=assigned_patient,
            doctor=doctor,
            diagnosis="Flu",
            treatment="Rest",
            admitted=True,
        )
        c2 = Consultation.objects.create(
            patient=assigned_patient,
            doctor=doctor,
            diagnosis="Cold",
            treatment="Fluids",
            admitted=True,
        )

        results = ConsultationService.bulk_discharge([c1.id, c2.id], doctor)

        assert len(results["success"]) == 2
        c1.refresh_from_db()
        c2.refresh_from_db()
        assert c1.discharged is True
        assert c2.discharged is True
        assert AuditLog.objects.filter(action="bulk_discharge").exists()

    def test_bulk_discharge_partial_failure(self, doctor, assigned_patient):
        import uuid

        fake_id = uuid.uuid4()
        results = ConsultationService.bulk_discharge([fake_id], doctor)
        assert len(results["failed"]) == 1
