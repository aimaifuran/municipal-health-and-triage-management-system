"""Seed comprehensive sample data for local testing and demos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Clinic, DoctorPatientAssignment, User, UserRole
from consultations.models import Consultation
from patients.models import Gender, Patient
from triage.models import SeverityLevel, TriageRecord, TriageStatus
from triage.services import PriorityCalculator

# Dev/demo only — override with DEMO_SEED_PASSWORD in environment for local setups.
DEMO_PASSWORD = "DemoPass123!"  # nosec B105


class Command(BaseCommand):
    help = "Seed clinics, users, patients, triage, and consultations for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove previously seeded sample data (PAT-SAMPLE-* / PAT-DEMO-*) before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_sample_data()

        clinics = self._seed_clinics()
        users = self._seed_users(clinics)
        patients = self._seed_patients(clinics, users)
        self._seed_assignments(users["doctors"], patients)
        triage_summary = self._seed_triage(patients, users["nurses"])
        consult_count = self._seed_consultations(patients, users["doctors"])

        self.stdout.write(self.style.SUCCESS("\n=== Sample data ready ==="))
        self.stdout.write(f"  Clinics: {len(clinics)}")
        self.stdout.write(f"  Patients: {len(patients)}")
        self.stdout.write(f"  Active triage records: {triage_summary['active']}")
        self.stdout.write(f"  Awaiting triage (no vitals yet): {triage_summary['awaiting']}")
        self.stdout.write(
            "  Severity mix — "
            f"Critical: {triage_summary['critical']}, "
            f"Moderate: {triage_summary['moderate']}, "
            f"Stable: {triage_summary['stable']}"
        )
        self.stdout.write(f"  Consultations: {consult_count}")
        self.stdout.write(self.style.WARNING(f"\n  Password for all demo users: {DEMO_PASSWORD}"))
        self._print_credentials(users)

    def _reset_sample_data(self) -> None:
        numbers = list(
            Patient.all_objects.filter(patient_number__startswith="PAT-SAMPLE-").values_list(
                "patient_number", flat=True
            )
        ) + ["PAT-DEMO-001"]
        patients = Patient.all_objects.filter(patient_number__in=numbers)
        TriageRecord.objects.filter(patient__in=patients).delete()
        Consultation.objects.filter(patient__in=patients).delete()
        DoctorPatientAssignment.objects.filter(patient__in=patients).delete()
        deleted, _ = patients.delete()
        self.stdout.write(
            self.style.WARNING(f"Removed {deleted} sample patient(s) and related records.")
        )

    def _seed_clinics(self) -> dict[str, Clinic]:
        specs = [
            {
                "key": "carigara",
                "name": "Montesclaros' Clinic",
                "address": "Real St, 6529 Carigara, Philippines, Carigara, Philippines, 6529",
                "municipality": "Carigara",
                "region": "Region VIII",
            },
            {
                "key": "barugo",
                "name": "Barugo Rural Health Unit",
                "address": "Barugo, Leyte, Brgy. Poblacion Dist. Iii, Barugo, Leyte, 6519",
                "municipality": "Barugo",
                "region": "Region VIII",
            },
            {
                "key": "capoocan",
                "name": "Capoocan Rural Health Unit",
                "address": "Capoocan, Leyte, Brgy. Poblacion Zone I, Capoocan, Leyte, 6530",
                "municipality": "Capoocan",
                "region": "Region VIII",
            },
        ]
        clinics: dict[str, Clinic] = {}
        for spec in specs:
            clinic, _ = Clinic.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "address": spec["address"],
                    "municipality": spec["municipality"],
                    "region": spec["region"],
                },
            )
            clinics[spec["key"]] = clinic
        return clinics

    def _seed_users(self, clinics: dict[str, Clinic]) -> dict:
        carigara = clinics["carigara"]
        barugo = clinics["barugo"]
        user_specs = [
            ("admin@mhtms.gov.ph", UserRole.SUPER_ADMIN, None, True, True),
            ("doctor@mhtms.gov.ph", UserRole.DOCTOR, carigara, False, False),
            ("doctor2@mhtms.gov.ph", UserRole.DOCTOR, barugo, False, False),
            ("nurse@mhtms.gov.ph", UserRole.NURSE, carigara, False, False),
            ("nurse2@mhtms.gov.ph", UserRole.NURSE, barugo, False, False),
            ("reception@mhtms.gov.ph", UserRole.RECEPTIONIST, carigara, False, False),
            ("reception2@mhtms.gov.ph", UserRole.RECEPTIONIST, barugo, False, False),
            ("api@mhtms.gov.ph", UserRole.API_CONSUMER, None, False, False),
        ]
        doctors: list[User] = []
        nurses: list[User] = []
        for email, role, clinic, is_super, is_staff in user_specs:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "role": role,
                    "clinic": clinic,
                    "first_name": email.split("@")[0].replace(".", " ").title(),
                    "is_verified": True,
                    "is_staff": is_staff or role == UserRole.SUPER_ADMIN,
                    "is_superuser": is_super,
                },
            )
            user.set_password(DEMO_PASSWORD)
            user.is_active = True
            user.clinic = clinic
            user.save()
            if role == UserRole.DOCTOR:
                doctors.append(user)
            if role == UserRole.NURSE:
                nurses.append(user)
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {action} user {email}"))
        return {
            "admin": User.objects.get(email="admin@mhtms.gov.ph"),
            "doctors": doctors,
            "nurses": nurses,
            "reception": User.objects.get(email="reception@mhtms.gov.ph"),
        }

    def _seed_patients(self, clinics: dict[str, Clinic], users: dict) -> list[Patient]:
        reception = users["reception"]
        patient_specs = [
            # Carigara — primary demo clinic (nurse@mhtms.gov.ph)
            (
                "PAT-SAMPLE-001",
                "Maria",
                "Santos",
                "1992-03-10",
                Gender.FEMALE,
                clinics["carigara"],
                "Fever, cough",
            ),
            (
                "PAT-SAMPLE-002",
                "Juan",
                "Dela Cruz",
                "1985-07-22",
                Gender.MALE,
                clinics["carigara"],
                "Chest pain",
            ),
            (
                "PAT-SAMPLE-003",
                "Ana",
                "Reyes",
                "2018-11-05",
                Gender.FEMALE,
                clinics["carigara"],
                "High fever",
            ),
            (
                "PAT-SAMPLE-004",
                "Pedro",
                "Garcia",
                "1958-01-30",
                Gender.MALE,
                clinics["carigara"],
                "Difficulty breathing",
            ),
            (
                "PAT-SAMPLE-005",
                "Liza",
                "Mendoza",
                "1998-09-14",
                Gender.FEMALE,
                clinics["carigara"],
                "Headache",
            ),
            (
                "PAT-SAMPLE-011",
                "Roberto",
                "Navarro",
                "1959-06-15",
                Gender.MALE,
                clinics["carigara"],
                "Chest pain, cold sweats",
            ),
            (
                "PAT-SAMPLE-012",
                "Corazon",
                "Bautista",
                "1967-04-03",
                Gender.FEMALE,
                clinics["carigara"],
                "Stroke symptoms",
            ),
            (
                "PAT-SAMPLE-013",
                "Ramon",
                "Castillo",
                "1964-11-20",
                Gender.MALE,
                clinics["carigara"],
                "Hypertension",
            ),
            (
                "PAT-SAMPLE-014",
                "Grace",
                "Flores",
                "1981-08-27",
                Gender.FEMALE,
                clinics["carigara"],
                "Cough",
            ),
            (
                "PAT-SAMPLE-015",
                "Jenny",
                "Aquino",
                "1996-02-14",
                Gender.FEMALE,
                clinics["carigara"],
                "Pregnancy",
            ),
            (
                "PAT-SAMPLE-016",
                "Teodoro",
                "Dizon",
                "1951-12-08",
                Gender.MALE,
                clinics["carigara"],
                "Weakness",
            ),
            (
                "PAT-SAMPLE-017",
                "Mark",
                "Salazar",
                "1990-07-19",
                Gender.MALE,
                clinics["carigara"],
                "Severe pain",
            ),
            (
                "PAT-SAMPLE-018",
                "Sophie",
                "Yu",
                "2021-05-22",
                Gender.FEMALE,
                clinics["carigara"],
                "Pediatric URI",
            ),
            (
                "PAT-SAMPLE-019",
                "Paul",
                "Chua",
                "1995-10-30",
                Gender.MALE,
                clinics["carigara"],
                "Follow-up",
            ),
            (
                "PAT-SAMPLE-020",
                "Darwin",
                "Perez",
                "1984-03-11",
                Gender.MALE,
                clinics["carigara"],
                "Trauma",
            ),
            (
                "PAT-SAMPLE-021",
                "Hannah",
                "Ong",
                "2000-01-25",
                Gender.FEMALE,
                clinics["carigara"],
                "Walk-in registration",
            ),
            (
                "PAT-SAMPLE-022",
                "Kevin",
                "Sy",
                "1987-09-09",
                Gender.MALE,
                clinics["carigara"],
                "Walk-in registration",
            ),
            (
                "PAT-SAMPLE-023",
                "Diana",
                "Co",
                "1978-12-02",
                Gender.FEMALE,
                clinics["carigara"],
                "Palpitations",
            ),
            (
                "PAT-DEMO-001",
                "Sofia",
                "Ramos",
                "1993-05-12",
                Gender.FEMALE,
                clinics["carigara"],
                "Mild cold",
            ),
            # Barugo
            (
                "PAT-SAMPLE-006",
                "Carlos",
                "Lim",
                "1960-12-01",
                Gender.MALE,
                clinics["barugo"],
                "Hypertension follow-up",
            ),
            (
                "PAT-SAMPLE-007",
                "Rosa",
                "Tan",
                "1995-04-18",
                Gender.FEMALE,
                clinics["barugo"],
                "Abdominal pain",
            ),
            (
                "PAT-SAMPLE-008",
                "Miguel",
                "Torres",
                "2005-06-25",
                Gender.MALE,
                clinics["barugo"],
                "Sprain",
            ),
            (
                "PAT-SAMPLE-024",
                "Alma",
                "Gutierrez",
                "1968-07-07",
                Gender.FEMALE,
                clinics["barugo"],
                "Diabetes follow-up",
            ),
            (
                "PAT-SAMPLE-025",
                "Victor",
                "Ramos",
                "1975-03-16",
                Gender.MALE,
                clinics["barugo"],
                "Unconscious",
            ),
            # Capoocan
            (
                "PAT-SAMPLE-009",
                "Elena",
                "Villanueva",
                "1988-08-08",
                Gender.FEMALE,
                clinics["capoocan"],
                "Prenatal check",
            ),
            (
                "PAT-SAMPLE-010",
                "James",
                "Go",
                "1990-02-17",
                Gender.MALE,
                clinics["capoocan"],
                "Sore throat",
            ),
        ]
        patients: list[Patient] = []
        for num, first, last, bday, gender, clinic, _notes in patient_specs:
            patient, created = Patient.objects.get_or_create(
                patient_number=num,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "birth_date": date.fromisoformat(bday),
                    "gender": gender,
                    "address": f"{clinic.municipality}, {clinic.region}",
                    "contact_number": "+639170000" + num[-3:],
                    "emergency_contact": f"Emergency contact for {first}",
                    "clinic": clinic,
                    "created_by": reception,
                },
            )
            patients.append(patient)
            if created:
                self.stdout.write(f"  Patient {num}: {first} {last}")
        return patients

    def _seed_assignments(self, doctors: list[User], patients: list[Patient]) -> None:
        carigara_doctor = doctors[0]
        for patient in patients:
            if patient.clinic_id == carigara_doctor.clinic_id:
                DoctorPatientAssignment.objects.get_or_create(
                    doctor=carigara_doctor,
                    patient=patient,
                    defaults={"is_active": True},
                )
        if len(doctors) > 1:
            barugo_doctor = doctors[1]
            for patient in patients:
                if patient.clinic_id == barugo_doctor.clinic_id:
                    DoctorPatientAssignment.objects.get_or_create(
                        doctor=barugo_doctor,
                        patient=patient,
                        defaults={"is_active": True},
                    )

    def _seed_triage(self, patients: list[Patient], nurses: list[User]) -> dict[str, int]:
        """Vitals keyed by patient_number — engine assigns severity. Omit key = awaiting triage."""
        triage_specs: dict[str, tuple[str, int, int, str, str, str]] = {
            # Legacy / baseline cases
            "PAT-SAMPLE-001": ("120/80", 72, 16, "98.0", "36.8", "Mild headache and fatigue"),
            "PAT-SAMPLE-002": (
                "145/95",
                110,
                22,
                "91.0",
                "38.5",
                "Chest pain, difficulty breathing",
            ),
            "PAT-SAMPLE-003": ("118/76", 88, 18, "96.5", "39.2", "High fever, cough, body aches"),
            "PAT-SAMPLE-004": (
                "88/60",
                132,
                32,
                "84.0",
                "38.9",
                "Chest pain, difficulty breathing, cold sweats",
            ),
            "PAT-SAMPLE-005": ("122/82", 76, 14, "99.0", "36.6", "Routine check, mild sore throat"),
            "PAT-DEMO-001": ("120/78", 80, 17, "98.0", "37.0", "Runny nose, mild cough"),
            # Clinical severity showcase (see docs/TRIAGE_SEVERITY_EVALUATION.md §10)
            "PAT-SAMPLE-011": (
                "88/60",
                132,
                32,
                "84.0",
                "38.9",
                "Chest pain, difficulty breathing, cold sweats",
            ),
            "PAT-SAMPLE-012": (
                "178/98",
                96,
                18,
                "95.0",
                "37.1",
                "Slurred speech and one-sided weakness",
            ),
            "PAT-SAMPLE-013": ("186/102", 116, 24, "93.0", "37.4", "Chest pain and cold sweats"),
            "PAT-SAMPLE-014": ("152/94", 124, 26, "91.0", "37.6", "Persistent cough and weakness"),
            "PAT-SAMPLE-015": (
                "142/90",
                110,
                22,
                "95.0",
                "37.0",
                "Pregnant patient with seizure and bleeding",
            ),
            "PAT-SAMPLE-016": (
                "148/92",
                108,
                22,
                "94.0",
                "39.2",
                "Elderly with dizziness and weakness",
            ),
            "PAT-SAMPLE-017": ("166/100", 104, 22, "92.0", "38.4", "Severe pain and dizziness"),
            "PAT-SAMPLE-018": ("102/68", 102, 24, "97.0", "37.5", "Runny nose and mild cough"),
            "PAT-SAMPLE-019": ("118/78", 74, 16, "99.0", "36.8", "Mild headache"),
            "PAT-SAMPLE-020": (
                "130/85",
                112,
                20,
                "96.0",
                "37.2",
                "Major trauma with severe bleeding",
            ),
            "PAT-SAMPLE-023": ("138/88", 105, 20, "94.0", "37.8", "Palpitations and severe pain"),
            # Barugo / Capoocan
            "PAT-SAMPLE-006": ("130/85", 82, 17, "97.0", "37.0", "Follow-up for hypertension"),
            "PAT-SAMPLE-007": ("125/80", 90, 20, "95.0", "38.0", "Abdominal pain, nausea"),
            "PAT-SAMPLE-008": ("118/78", 70, 15, "99.5", "36.7", "Ankle sprain, swelling"),
            "PAT-SAMPLE-009": ("115/75", 68, 16, "98.5", "36.9", "Prenatal vitals normal"),
            "PAT-SAMPLE-010": ("122/80", 74, 16, "97.5", "37.2", "Sore throat, low fever"),
            "PAT-SAMPLE-024": (
                "128/82",
                78,
                16,
                "97.0",
                "36.9",
                "Diabetic follow-up, mild fatigue",
            ),
            "PAT-SAMPLE-025": (
                "100/65",
                118,
                20,
                "92.0",
                "36.5",
                "Found unconscious, unresponsive",
            ),
            # PAT-SAMPLE-021, PAT-SAMPLE-022 intentionally omitted — awaiting nurse triage
        }

        summary = {
            "active": 0,
            "awaiting": 0,
            "critical": 0,
            "moderate": 0,
            "stable": 0,
        }
        for patient in patients:
            spec = triage_specs.get(patient.patient_number)
            if not spec:
                summary["awaiting"] += 1
                continue

            nurse = nurses[0] if patient.clinic.municipality == "Carigara" else nurses[-1]
            bp, hr, rr, o2, temp, symptoms = spec
            TriageRecord.objects.filter(patient=patient, is_active=True).update(
                is_active=False,
                triage_status=TriageStatus.COMPLETED,
            )
            assessment = PriorityCalculator.assess(
                oxygen_saturation=Decimal(o2),
                body_temperature=Decimal(temp),
                heart_rate=hr,
                respiratory_rate=rr,
                blood_pressure=bp,
                symptoms=symptoms,
                patient=patient,
            )
            calc_severity = assessment.severity_level
            status = (
                TriageStatus.ESCALATED
                if calc_severity == SeverityLevel.CRITICAL
                else TriageStatus.WAITING
            )
            TriageRecord.objects.create(
                patient=patient,
                nurse=nurse,
                blood_pressure=bp,
                heart_rate=hr,
                respiratory_rate=rr,
                oxygen_saturation=Decimal(o2),
                body_temperature=Decimal(temp),
                symptoms=symptoms,
                severity_level=calc_severity,
                priority_score=assessment.priority_score,
                triage_status=status,
                is_active=True,
            )
            summary["active"] += 1
            if calc_severity == SeverityLevel.CRITICAL:
                summary["critical"] += 1
            elif calc_severity == SeverityLevel.MODERATE:
                summary["moderate"] += 1
            else:
                summary["stable"] += 1
            self.stdout.write(
                f"  Triage {patient.patient_number}: {assessment.triage_tier.value} "
                f"-> {calc_severity} (score {assessment.priority_score})"
            )

        return summary

    def _seed_consultations(self, patients: list[Patient], doctors: list[User]) -> int:
        now = timezone.now()
        consult_specs = [
            (
                0,
                "Acute bronchitis",
                "Rest, fluids, bronchodilator",
                "Salbutamol inhaler",
                True,
                False,
            ),
            (
                1,
                "Suspected angina",
                "ECG, aspirin, admit for observation",
                "Aspirin 81mg",
                True,
                False,
            ),
            (2, "Viral fever", "Antipyretics, hydration", "Paracetamol 500mg", False, False),
            (
                3,
                "Acute asthma exacerbation",
                "Nebulizer, oxygen therapy",
                "Prednisone 40mg",
                True,
                False,
            ),
            (
                4,
                "Tension headache",
                "Analgesics, stress management",
                "Ibuprofen 400mg",
                False,
                True,
            ),
            (
                5,
                "Hypertension Stage 2",
                "Lifestyle modification, medication",
                "Losartan 50mg daily",
                True,
                False,
            ),
        ]
        count = 0
        carigara_doctor = doctors[0]
        for idx, (p_idx, dx, tx, rx, admitted, discharged) in enumerate(consult_specs):
            if p_idx >= len(patients):
                break
            patient = patients[p_idx]
            doctor = (
                carigara_doctor if patient.clinic_id == carigara_doctor.clinic_id else doctors[1]
            )
            consultation, created = Consultation.objects.get_or_create(
                patient=patient,
                doctor=doctor,
                diagnosis=dx,
                defaults={
                    "treatment": tx,
                    "prescription": rx,
                    "admitted": admitted,
                    "discharged": discharged,
                    "consultation_notes": f"Sample consultation {idx + 1}",
                    "admitted_at": now if admitted else None,
                    "discharged_at": now if discharged else None,
                },
            )
            if not created:
                consultation.treatment = tx
                consultation.prescription = rx
                consultation.admitted = admitted
                consultation.discharged = discharged
                consultation.admitted_at = now if admitted else None
                consultation.discharged_at = now if discharged else None
                consultation.save()
            count += 1
        return count

    def _print_credentials(self, users: dict) -> None:
        self.stdout.write("\n  Demo accounts:")
        for email in User.objects.filter(email__endswith="@mhtms.gov.ph").values_list(
            "email", flat=True
        ):
            self.stdout.write(f"    • {email}")
        self.stdout.write("\n  Re-seed anytime: python manage.py seed_demo --reset")
        self.stdout.write(
            "  Nurse login (Carigara): nurse@mhtms.gov.ph — "
            "queue shows Critical/Moderate/Stable mix"
        )
        self.stdout.write(
            "  Awaiting triage: PAT-SAMPLE-021, PAT-SAMPLE-022 (register vitals in dashboard)\n"
        )
