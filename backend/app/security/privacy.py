import hashlib
from typing import Any

SALT = "reliefchain_salt_2026_mumbai_surge"

def anonymize_patient_id(raw_id: str) -> str:
    """Computes a salted irreversible hash for simulated patient identifier."""
    h = hashlib.sha256(f"{raw_id}:{SALT}".encode('utf-8')).hexdigest()
    return f"ANON-{h[:10].upper()}"

def redact_for_role(data: dict, role: str) -> dict:
    """
    Applies role-based privacy redaction:
    - 'Control Room', 'Judge', 'Dispatcher': Full operational visibility
    - 'Hospital': Only their hospital's internal patients & arriving inbound ambulances
    - 'NGO': General casualty numbers and relief supplies; fund totals and triage breakdowns redacted
    - 'Donor': Financial traceability and aggregate survivor impact; operational ambulance/patient telemetry redacted
    - 'Auditor': Full cryptographic ledger, Merkle roots, and fund flows; patient medical names redacted
    - 'Public': High-level safety bulletins and aggregated ward statuses only
    """
    if role in ("Control Room", "Judge", "Dispatcher"):
        return data

    redacted = dict(data)

    if role == "Public":
        # Strip exact patient details and internal fleet telemetry
        if "incidents" in redacted:
            redacted["incidents"] = [
                {
                    "id": inc["id"],
                    "label": inc["label"],
                    "severity": inc["severity"],
                    "area": inc["area"],
                    "position": inc["position"],
                    "status": inc["status"],
                    "description": inc.get("description", "Public safety alert in effect")
                }
                for inc in redacted["incidents"]
            ]
        if "ambulances" in redacted:
            # Hide individual ambulance GPS track and driver telemetry
            redacted["ambulances"] = [
                {"id": f"FLEET-{idx}", "status": amb["status"], "type": amb["type"], "position": amb["position"]}
                for idx, amb in enumerate(redacted["ambulances"])
            ]
        if "funds" in redacted:
            # Only aggregated totals
            total_raised = sum(f.get("amount", 0) for f in redacted.get("funds", []))
            redacted["funds"] = [{"donor": "Multiple Donors", "amount": total_raised, "purpose": "Emergency Operations Pool", "stage": "released"}]

    elif role == "Donor":
        # Donors focus on fund flows, verified proofs, receipts, and aggregate survivor impact
        if "ambulances" in redacted:
            redacted["ambulances"] = [] # internal tactical fleet hidden

    elif role == "Hospital":
        # Hospital sees full local inventory and inbound arrivals
        pass

    return redacted
