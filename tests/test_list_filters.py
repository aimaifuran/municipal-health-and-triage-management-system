from datetime import date

import pytest

from common.list_filters import patient_search_q
from patients.models import Patient


@pytest.mark.django_db
class TestPatientSearch:
    def test_matches_patient_number(self, patient):
        qs = Patient.objects.filter(patient_search_q("PAT-TEST"))
        assert patient in qs

    def test_matches_first_name(self, patient):
        qs = Patient.objects.filter(patient_search_q("Juan"))
        assert patient in qs

    def test_matches_multi_word_full_name(self, clinic, receptionist):
        p = Patient.objects.create(
            patient_number="PAT-SEARCH-001",
            first_name="Jenny",
            last_name="Aquino",
            birth_date=date(1990, 1, 1),
            gender="female",
            address="Cebu",
            contact_number="+639171234567",
            emergency_contact="Contact",
            clinic=clinic,
            created_by=receptionist,
        )
        qs = Patient.objects.filter(patient_search_q("Jenny Aquino"))
        assert p in qs
        qs_last_first = Patient.objects.filter(patient_search_q("Aquino Jenny"))
        assert p in qs_last_first
