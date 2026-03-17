"""PII masking utilities for log safety."""


def mask_phone(phone: str) -> str:
    """Mask phone number for logging: 138****1234."""
    if not phone or len(phone) < 7:
        return "***"
    return phone[:3] + "****" + phone[-4:]


def mask_email(email: str) -> str:
    """Mask email address for logging: u***@example.com."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"
