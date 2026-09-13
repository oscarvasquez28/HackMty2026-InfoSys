"""
Data Masking and PII Redaction Engine for Polar Forensic Auditor.
Protects sensitive financial, banking, and personal identifiable information (PII)
before transmission to AI agents, LLMs, and external webhook integrations.
"""

import re
from typing import Any, Dict, List, Union

# Regex patterns for scanning free-text fields
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
CLABE_REGEX = re.compile(r"\b(\d{4})\d{10}(\d{4})\b")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{2,3}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}")


def mask_clabe(clabe: Any) -> str:
    """Masks an 18-digit bank CLABE, showing only first 4 and last 4 digits."""
    if not clabe:
        return ""
    val = str(clabe).strip()
    if len(val) >= 10:
        return f"{val[:4]}{'*' * (len(val) - 8)}{val[-4:]}"
    return f"{val[:2]}{'*' * max(len(val) - 4, 2)}{val[-2:]}" if len(val) > 4 else "****"


def mask_email(email: Any) -> str:
    """Masks an email address (e.g. user@example.com -> u***r@example.com)."""
    if not email:
        return ""
    val = str(email).strip()
    if "@" not in val:
        return "****"
    user_part, domain = val.split("@", 1)
    if len(user_part) <= 2:
        masked_user = f"{user_part[0]}***" if user_part else "***"
    else:
        masked_user = f"{user_part[0]}***{user_part[-1]}"
    return f"{masked_user}@{domain}"


def mask_phone(phone: Any) -> str:
    """Masks a phone number, preserving only the last 4 digits."""
    if not phone:
        return ""
    val = re.sub(r"[^\d]", "", str(phone).strip())
    if len(val) >= 4:
        return f"******{val[-4:]}"
    return "******"


def mask_address(addr: Any) -> str:
    """Masks physical street address to protect personal domicile location."""
    if not addr:
        return ""
    val = str(addr).strip()
    # Keep country or city if discernible, mask street numbers and interior info
    return "[DIRECCIÓN PROTEGIDA / REDACTED ADDRESS]"


def mask_ssn(ssn: Any) -> str:
    """Masks social security, CURP, or personal tax identification number."""
    if not ssn:
        return ""
    val = str(ssn).strip()
    if len(val) >= 4:
        return f"***-**-{val[-4:]}"
    return "***-**-****"


def mask_free_text(text: str) -> str:
    """Scans free-text descriptions and masks emails and CLABEs."""
    if not text:
        return ""
    # Mask emails in text
    def _sub_email(m):
        return mask_email(m.group(0))
    masked = EMAIL_REGEX.sub(_sub_email, text)

    # Mask 18-digit CLABEs in text
    def _sub_clabe(m):
        return f"{m.group(1)}**********{m.group(2)}"
    masked = CLABE_REGEX.sub(_sub_clabe, masked)
    return masked


# Sensitive field mapping to masking handlers
SENSITIVE_FIELD_HANDLERS = {
    "bank_clabe": mask_clabe,
    "from_clabe": mask_clabe,
    "to_clabe": mask_clabe,
    "contact_email": mask_email,
    "personal_email": mask_email,
    "work_email": mask_email,
    "company_email": mask_email,
    "alternate_email": mask_email,
    "primary_phone": mask_phone,
    "work_phone": mask_phone,
    "cell_phone": mask_phone,
    "alternate_phone": mask_phone,
    "home_phone": mask_phone,
    "address": mask_address,
    "street_addr": mask_address,
    "ssn": mask_ssn,
    "birth_date": lambda x: f"{str(x)[:4]}-**-**" if len(str(x)) >= 4 else "****-**-**",
}


def mask_sensitive_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a copy of a database record dictionary with all sensitive PII fields masked.
    Preserves identifiers needed for evidence reconciliation (UUIDs, RFCs, entry_id, po_id).
    """
    masked = {}
    for key, val in record.items():
        if val is None:
            masked[key] = None
        elif key in SENSITIVE_FIELD_HANDLERS:
            masked[key] = SENSITIVE_FIELD_HANDLERS[key](val)
        elif isinstance(val, str) and key in ("description", "reference", "concepto_text", "note", "sentence", "scope_text"):
            masked[key] = mask_free_text(val)
        elif isinstance(val, dict):
            masked[key] = mask_sensitive_record(val)
        elif isinstance(val, list):
            masked[key] = [
                mask_sensitive_record(item) if isinstance(item, dict) else item
                for item in val
            ]
        else:
            masked[key] = val
    return masked


def mask_sensitive_payload(payload: Any) -> Any:
    """Recursively traverses any dictionary or list structure and masks sensitive fields."""
    if isinstance(payload, dict):
        return mask_sensitive_record(payload)
    if isinstance(payload, list):
        return [mask_sensitive_payload(item) for item in payload]
    return payload
