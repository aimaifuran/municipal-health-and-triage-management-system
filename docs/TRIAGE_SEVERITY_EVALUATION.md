# Triage Severity Evaluation

This document describes how the **Municipal Health & Triage Management System (MHTMS)** automatically determines patient severity when a nurse submits vitals and symptoms.

**Implementation:** `triage/severity_engine.py` (`ClinicalTriageEngine`) via `triage/services.py` (`PriorityCalculator`).

**There is no manual severity dropdown.** Severity is always computed server-side.

---

## 1. Overview

| Step | What happens |
|------|----------------|
| 1 | Nurse enters vitals + symptoms (and patient demographics already on file). |
| 2 | Engine evaluates vitals, symptom text, and age-related risk. |
| 3 | System assigns an internal **triage tier** (RED / ORANGE / YELLOW / GREEN). |
| 4 | Tier maps to stored **severity level** and **priority score** (0–100). |
| 5 | Queue sorts by priority score; critical cases are escalated. |

---

## 2. Severity levels (stored in database)

| Severity level | Display label | Typical triage tier | Queue behavior |
|----------------|---------------|---------------------|----------------|
| `critical` | Critical | RED | Status set to **Escalated** |
| `moderate` | Moderate | ORANGE or YELLOW | **Waiting** (higher score = seen sooner) |
| `stable` | Stable | GREEN | **Waiting** |

---

## 3. Triage tiers (clinical acuity)

| Tier | Clinical meaning | Maps to severity | Priority score (typical) |
|------|------------------|------------------|---------------------------|
| **RED** | Life-threatening — intervene immediately | Critical | 80–100 |
| **ORANGE** | Potentially serious — urgent physician review | Moderate | 55–79 |
| **YELLOW** | Stable but needs medical assessment | Moderate | 30–54 |
| **GREEN** | Minor / non-urgent | Stable | 0–29 |

**Safety rule:** If the engine is unsure between two tiers, it selects the **higher** acuity.

---

## 4. Inputs used

| Input | Source | Used for |
|-------|--------|----------|
| Blood pressure | Nurse form | Systolic thresholds, shock/hypertension |
| Heart rate (bpm) | Nurse form | Tachycardia / bradycardia |
| Respiratory rate | Nurse form | Airway/breathing distress |
| SpO₂ (%) | Nurse form | Hypoxia |
| Temperature (°C) | Nurse form | Fever, hypothermia, sepsis patterns |
| Symptoms | Nurse form (free text) | RED/ORANGE phrase matching, pregnancy, chronic illness keywords |
| Age | Patient `birth_date` | Elderly, infant, pediatric risk adjustment |
| Sex | Patient `gender` | Available for future rules |

Pregnancy and chronic conditions are inferred from **keywords in the symptoms field** (e.g. “pregnant”, “diabetes”) unless dedicated fields are added later.

---

## 5. Vital sign thresholds

### 5.1 Oxygen saturation (SpO₂)

| Value | Acuity | Effect |
|-------|--------|--------|
| &lt; 90% | **RED (critical)** | Forced highest tier; hypoxia finding |
| 90–93% | High risk | Adds risk points; possible respiratory compromise |
| ≥ 94% | — | Normal range (no penalty from SpO₂ alone) |

### 5.2 Heart rate (bpm)

| Value | Acuity | Effect |
|-------|--------|--------|
| &gt; 130 or &lt; 40 | **RED** | Forced highest tier |
| &gt; 120 or &lt; 50 | High risk | Adds risk points |
| 60–100 (approx.) | — | Normal range |

### 5.3 Temperature (°C)

| Value | Acuity | Effect |
|-------|--------|--------|
| &lt; 35.0 | **RED** | Hypothermia |
| ≥ 39.5 | High risk | Severe fever / sepsis risk |
| ≥ 38.0 | Moderate | Adds risk points |
| High fever + confusion/altered mental status in symptoms | **RED** | Possible sepsis or CNS infection |

### 5.4 Blood pressure (systolic, mmHg)

| Value | Acuity | Effect |
|-------|--------|--------|
| &lt; 90 | **RED** | Shock / hypotension |
| &gt; 200 | **RED** | Critical hypertension |
| &gt; 180 | High risk | Hypertensive emergency risk |
| &gt; 180 **with chest pain** in symptoms | **RED** | Possible acute coronary syndrome |
| 160–180 | Moderate | Adds risk points |

### 5.5 Respiratory rate (per minute)

| Value | Acuity | Effect |
|-------|--------|--------|
| &gt; 30 or &lt; 8 | **RED** | Critical breathing pattern |
| &gt; 24 or &lt; 10 | High risk | Adds risk points |

---

## 6. Symptom-based RED flags (substring match)

If **any** phrase below appears in the symptoms text (case-insensitive), the case is treated as **RED** or heavily upgraded:

| Category | Example phrases |
|----------|-----------------|
| Airway / breathing | difficulty breathing, respiratory distress, shortness of breath, cyanosis, choking, gasping |
| Circulation | severe bleeding, hemorrhage, shock, no pulse |
| Neurological | unconscious, unresponsive, seizure, stroke, altered mental status, slurred speech, one-sided weakness |
| Cardiac | chest pain, cardiac arrest |
| Trauma | major trauma, gunshot, stab wound, severe burns, head injury |
| Infection | sepsis, septic, meningitis |
| Obstetric | severe vaginal bleeding, eclampsia |
| Toxicology | overdose, poisoning |

Additional **ORANGE** phrases (e.g. severe pain, palpitations, dizziness) add risk points but may not alone force RED.

---

## 7. Special populations (risk adjustment)

| Population | How detected | Effect |
|------------|--------------|--------|
| Elderly (≥ 65 years) | Age from birth date | +8 risk points |
| Infant (&lt; 1 year) | Age from birth date | +12 risk points |
| Child (&lt; 5 years) | Age from birth date | +6 risk points |
| Pregnancy | Keywords in symptoms | +10 risk points; obstetric emergencies force RED |
| Chronic illness | Keywords (diabetes, hypertension, heart disease, etc.) | +6 risk points |

---

## 8. Combined findings

| Rule | Effect |
|------|--------|
| Multiple moderate vital abnormalities (≥ 2) | +15 risk points; may raise tier |
| Several ORANGE symptom phrases | Up to +24 risk points |
| Symptom suggests stroke/cardiac/breathing but vitals look “okay” | Tier is **not** downgraded below ORANGE |

---

## 9. Priority score and final severity

1. Engine starts from a **base score** for the assigned tier (RED highest, GREEN lowest).
2. **Risk points** from vitals, symptoms, and population factors adjust the score (capped 0–100).
3. **RED** tier always yields score **≥ 80** and severity **Critical**.
4. Final **severity level** is saved on the triage record; **priority score** controls queue order.

| Priority score | Usual interpretation |
|----------------|----------------------|
| 80–100 | Critical emergency |
| 55–79 | High priority |
| 30–54 | Moderate |
| 0–29 | Low / stable |

---

## 10. Example patient dataset (for validation)

Use the table below as a quick benchmark when checking severity improvements after rule updates.

| Case | Age | Vitals / Symptoms snapshot | Expected tier | Stored severity | Priority band |
|------|-----|----------------------------|---------------|-----------------|---------------|
| A — Critical hypoxia + shock | 67 | SpO₂ 84, HR 132, RR 32, SBP 88, chest pain + difficulty breathing | RED | Critical | 80–100 |
| B — Stroke pattern | 58 | SpO₂ 95, HR 96, RR 18, SBP 178, slurred speech + one-sided weakness | RED | Critical | 80–100 |
| C — Hypertensive cardiac risk | 61 | SpO₂ 93, HR 116, RR 24, SBP 186, chest pain + cold sweats | RED | Critical | 80–100 |
| D — High-risk respiratory | 43 | SpO₂ 91, HR 124, RR 26, SBP 152, persistent cough + weakness | ORANGE | Moderate | 55–79 |
| E — Obstetric emergency signal | 29 | SpO₂ 95, HR 110, RR 22, SBP 142, pregnant + seizure + bleeding | RED | Critical | 80–100 |
| F — Febrile elderly | 74 | SpO₂ 94, HR 108, RR 22, SBP 148, temp 39.2, dizziness + weakness | ORANGE | Moderate | 55–79 |
| G — Moderate multi-abnormal | 35 | SpO₂ 92, HR 104, RR 22, SBP 166, temp 38.4, severe pain | ORANGE or YELLOW | Moderate | 30–79 |
| H — Pediatric mild URI | 4 | SpO₂ 97, HR 102, RR 24, SBP 102, runny nose + mild cough | YELLOW or GREEN | Moderate or Stable | 20–54 |
| I — Stable routine follow-up | 30 | SpO₂ 99, HR 74, RR 16, SBP 118, mild headache | GREEN | Stable | 0–29 |
| J — Severe trauma keyword | 41 | SpO₂ 96, HR 112, RR 20, SBP 130, major trauma + bleeding | RED | Critical | 80–100 |

### Notes for interpreting this dataset

- Some rows intentionally allow a range (for example ORANGE or YELLOW) because cumulative risk-point effects can shift with tuning.
- Any **explicit RED flag symptom** should remain RED even if most vitals look near normal.
- This table is designed for quick regression checks after triage-rule changes.

---

## 11. What staff see in the app

| UI element | Meaning |
|------------|---------|
| **Critical / Moderate / Stable** badge | Stored `severity_level` |
| **Priority number** | `priority_score` (higher = more urgent) |
| Pulsing indicator | `critical` severity only |

Full tier labels (RED/ORANGE/YELLOW/GREEN) appear in **audit logs** after each triage (`triage_tier`, `triage_reasoning`, etc.), not as a separate nurse input.

---

## 12. API behavior

| Endpoint | Severity fields |
|----------|-----------------|
| `POST /api/v1/triage/` | `severity_level` and `priority_score` are **read-only** in responses |
| `PATCH /api/v1/triage/{id}/` | Sending `severity_level` alone can override (API only); vitals update **recalculates** severity |

---

## 13. Disclaimer

This engine supports **triage prioritization** only. It does **not** provide a definitive diagnosis. When in doubt, the system chooses **higher acuity** for patient safety.

For code changes to scoring rules, edit only `triage/severity_engine.py` and related tests in `tests/test_models.py`.
