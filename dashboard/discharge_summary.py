"""Discharged patient summary context and PDF generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO

from django.db.models import Prefetch, QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.models import User
from consultations.models import Consultation
from security.access import AccessControlService
from triage.models import TriageRecord


@dataclass(frozen=True)
class DischargeSummaryContext:
    consultation: Consultation
    patient: object
    triage: TriageRecord | None
    document_ref: str
    generated_at: timezone.datetime


def _discharged_consultation_queryset() -> QuerySet:
    return (
        Consultation.objects.filter(admitted=True, discharged=True)
        .select_related("patient", "patient__clinic", "doctor")
        .prefetch_related(
            Prefetch(
                "patient__triage_records",
                queryset=TriageRecord.objects.select_related("nurse").order_by("-created_at"),
            )
        )
    )


def get_discharged_consultation(user: User, pk, request: HttpRequest | None = None) -> Consultation:
    consultation = get_object_or_404(
        AccessControlService.filter_consultations_for_user(
            user, _discharged_consultation_queryset()
        ),
        pk=pk,
    )
    AccessControlService.assert_patient_access(user, consultation.patient, request)
    return consultation


def get_latest_triage(consultation: Consultation) -> TriageRecord | None:
    triage_records = list(consultation.patient.triage_records.all())
    return triage_records[0] if triage_records else None


def build_discharge_summary_context(consultation: Consultation) -> DischargeSummaryContext:
    triage = get_latest_triage(consultation)
    discharged = consultation.discharged_at or timezone.now()
    ref_date = timezone.localtime(discharged).strftime("%Y%m%d")
    document_ref = f"{consultation.patient.patient_number}-DS-{ref_date}"
    return DischargeSummaryContext(
        consultation=consultation,
        patient=consultation.patient,
        triage=triage,
        document_ref=document_ref,
        generated_at=timezone.now(),
    )


def patient_age_years(birth_date: date, on_date: date | None = None) -> int:
    on = on_date or timezone.localdate()
    years = on.year - birth_date.year
    if (on.month, on.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def _pdf_cell(text: str) -> str:
    if not text:
        return "—"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _label_value_table(rows: list[tuple[str, str]], col_widths=None) -> Table:
    data = [
        [
            Paragraph(f"<b>{_pdf_cell(label)}</b>", _STYLES["label"]),
            Paragraph(_pdf_cell(value), _STYLES["body"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=col_widths or [1.55 * inch, 5.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ]
        )
    )
    return table


def _section_heading(title: str) -> Paragraph:
    return Paragraph(title, _STYLES["section"])


_STYLES: dict[str, ParagraphStyle] = {}


def _init_styles() -> None:
    global _STYLES
    if _STYLES:
        return
    base = getSampleStyleSheet()
    _STYLES["title"] = ParagraphStyle(
        "DocTitle",
        parent=base["Heading1"],
        fontSize=13,
        alignment=TA_CENTER,
        spaceAfter=6,
        textColor=colors.HexColor("#0f172a"),
    )
    _STYLES["subtitle"] = ParagraphStyle(
        "DocSubtitle",
        parent=base["Normal"],
        fontSize=9,
        alignment=TA_CENTER,
        spaceAfter=2,
        textColor=colors.HexColor("#334155"),
    )
    _STYLES["section"] = ParagraphStyle(
        "Section",
        parent=base["Heading2"],
        fontSize=10,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#0f4c81"),
    )
    _STYLES["body"] = ParagraphStyle(
        "Body",
        parent=base["Normal"],
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
    )
    _STYLES["label"] = ParagraphStyle(
        "Label",
        parent=base["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )
    _STYLES["footer"] = ParagraphStyle(
        "Footer",
        parent=base["Normal"],
        fontSize=7,
        leading=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748b"),
    )
    _STYLES["sig"] = ParagraphStyle(
        "Sig",
        parent=base["Normal"],
        fontSize=9,
        alignment=TA_CENTER,
    )


def render_discharge_summary_pdf(ctx: DischargeSummaryContext) -> bytes:
    _init_styles()
    patient = ctx.patient
    consultation = ctx.consultation
    clinic = patient.clinic
    triage = ctx.triage
    doctor = consultation.doctor
    doctor_name = doctor.full_name

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"Discharge Summary — {patient.patient_number}",
    )
    story: list = []

    story.append(Paragraph("Republic of the Philippines", _STYLES["subtitle"]))
    story.append(Paragraph("Department of Health", _STYLES["subtitle"]))
    story.append(Paragraph(_pdf_cell(clinic.name), _STYLES["title"]))
    story.append(
        Paragraph(
            _pdf_cell(f"{clinic.address}, {clinic.municipality}, {clinic.region}"),
            _STYLES["subtitle"],
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph("OUTPATIENT DISCHARGE SUMMARY", _STYLES["title"]))
    story.append(
        Paragraph(
            f"Document Ref. No.: <b>{_pdf_cell(ctx.document_ref)}</b>",
            _STYLES["subtitle"],
        )
    )
    story.append(Spacer(1, 8))

    visit_date = consultation.discharged_at or consultation.admitted_at
    visit_local = timezone.localtime(visit_date) if visit_date else None
    age = patient_age_years(patient.birth_date, visit_local.date() if visit_local else None)

    story.append(_section_heading("I. Patient Information"))
    story.append(
        _label_value_table(
            [
                ("Full name", patient.full_name),
                ("Patient ID", patient.patient_number),
                ("Date of birth", patient.birth_date.strftime("%B %d, %Y")),
                ("Age", f"{age} years"),
                ("Sex", patient.get_gender_display()),
                ("Contact number", patient.contact_number),
                ("Emergency contact", patient.emergency_contact),
                ("Address", patient.address),
            ]
        )
    )

    if triage:
        story.append(_section_heading("II. Triage & Vital Signs"))
        story.append(
            _label_value_table(
                [
                    (
                        "Date / time of triage",
                        timezone.localtime(triage.created_at).strftime("%B %d, %Y %I:%M %p"),
                    ),
                    ("Severity", triage.get_severity_level_display()),
                    ("Blood pressure", triage.blood_pressure),
                    ("Heart rate", f"{triage.heart_rate} bpm"),
                    ("Respiratory rate", f"{triage.respiratory_rate} /min"),
                    ("SpO₂", f"{triage.oxygen_saturation}%"),
                    ("Temperature", f"{triage.body_temperature} °C"),
                    ("Chief complaint / symptoms", triage.symptoms),
                ]
            )
        )
        section_num = "III"
    else:
        section_num = "II"

    admitted_str = (
        timezone.localtime(consultation.admitted_at).strftime("%B %d, %Y %I:%M %p")
        if consultation.admitted_at
        else "—"
    )
    discharged_str = (
        timezone.localtime(consultation.discharged_at).strftime("%B %d, %Y %I:%M %p")
        if consultation.discharged_at
        else "—"
    )

    story.append(_section_heading(f"{section_num}. Clinical Record & Disposition"))
    story.append(
        _label_value_table(
            [
                ("Attending physician", doctor_name),
                ("Date / time admitted", admitted_str),
                ("Date / time discharged", discharged_str),
                ("Disposition", "Discharged — fit for release from municipal health facility care"),
            ]
        )
    )
    story.append(Spacer(1, 6))
    story.append(_section_heading("Diagnosis / Clinical impression"))
    story.append(Paragraph(_pdf_cell(consultation.diagnosis), _STYLES["body"]))
    story.append(Spacer(1, 6))
    story.append(_section_heading("Treatment / Procedures rendered"))
    story.append(Paragraph(_pdf_cell(consultation.treatment), _STYLES["body"]))
    if consultation.prescription:
        story.append(Spacer(1, 6))
        story.append(_section_heading("Medications prescribed"))
        story.append(Paragraph(_pdf_cell(consultation.prescription), _STYLES["body"]))
    if consultation.consultation_notes:
        story.append(Spacer(1, 6))
        story.append(_section_heading("Additional notes"))
        story.append(Paragraph(_pdf_cell(consultation.consultation_notes), _STYLES["body"]))

    story.append(Spacer(1, 24))
    sig_data = [
        ["", ""],
        [Paragraph(f"<b>{_pdf_cell(doctor_name)}</b>", _STYLES["sig"]), ""],
        [
            Paragraph("Attending Physician", _STYLES["sig"]),
            Paragraph("Date signed", _STYLES["sig"]),
        ],
        [
            Paragraph(
                discharged_str.split(" ")[0] if discharged_str != "—" else "_______________",
                _STYLES["sig"],
            ),
            "",
        ],
    ]
    sig_table = Table(sig_data, colWidths=[3.4 * inch, 3.4 * inch])
    sig_table.setStyle(TableStyle([("LINEABOVE", (0, 1), (0, 1), 0.75, colors.black)]))
    story.append(sig_table)

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            "This document summarizes care provided at the municipal health facility listed above. "
            "The patient should follow prescribed medications and return immediately if symptoms worsen. "
            "This summary does not replace specialist referral records or hospital discharge papers when applicable.",
            _STYLES["footer"],
        )
    )
    generated = timezone.localtime(ctx.generated_at).strftime("%B %d, %Y %I:%M %p")
    story.append(Paragraph(f"Generated by MHTMS on {generated}.", _STYLES["footer"]))

    doc.build(story)
    return buffer.getvalue()


def discharge_summary_filename(ctx: DischargeSummaryContext) -> str:
    patient_number = ctx.patient.patient_number.replace("/", "-")
    date_part = timezone.localtime(ctx.consultation.discharged_at or ctx.generated_at).strftime(
        "%Y%m%d"
    )
    return f"Discharge-Summary-{patient_number}-{date_part}.pdf"
