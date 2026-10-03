"""
backend/app/security/auth.py
============================
Lightweight zero-dependency JWT implementation (RFC 7519 HMAC-SHA256)
and FastAPI RBAC persona authentication.

Seeded Personas:
- Control Room:   token for full operations
- Judge:          token for evaluation & audit
- Auditor:        token for ledger verification & tamper testing
- Evaluator:      token for stress testing & benchmarking
- Hospital:       token for hospital view
- NGO:            token for supply view
- Donor:          token for fund flow view
- Public:         unauthenticated / public view
"""

import hmac
import hashlib
import json
import base64
import time
from typing import Optional
from fastapi import Header, HTTPException, Depends

JWT_SECRET = "reliefchain-mumbai-surge-secret-key-2026-zero-external-key"

PERSONAS = {
    "control_room": {"username": "operator_mumbai", "role": "Control Room", "name": "Disaster Ops Commander"},
    "judge":        {"username": "hackathon_judge", "role": "Judge",        "name": "SDMA Evaluation Judge"},
    "auditor":      {"username": "mumbai_auditor",  "role": "Auditor",      "name": "Independent Cryptographic Auditor"},
    "evaluator":    {"username": "system_evaluator","role": "Evaluator",    "name": "Stress & Invariants Evaluator"},
    "hospital":     {"username": "kem_director",    "role": "Hospital",     "name": "KEM Medical Superintendent"},
    "ngo":          {"username": "relief_ngo",      "role": "NGO",          "name": "SEWA Relief Coordinator"},
    "donor":        {"username": "tata_trusts",     "role": "Donor",        "name": "CSR Disaster Fund Lead"},
    "public":       {"username": "citizen",         "role": "Public",       "name": "Public Citizen"},
}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(s: str) -> bytes:
    padding = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_jwt_token(payload: dict, expires_in_seconds: int = 86400 * 7) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload_copy = dict(payload)
    payload_copy["exp"] = int(time.time()) + expires_in_seconds
    payload_copy["iat"] = int(time.time())

    h_bytes = json.dumps(header, separators=(',', ':')).encode('utf-8')
    p_bytes = json.dumps(payload_copy, separators=(',', ':')).encode('utf-8')

    segments = f"{_b64url_encode(h_bytes)}.{_b64url_encode(p_bytes)}"
    sig = hmac.new(JWT_SECRET.encode('utf-8'), segments.encode('ascii'), hashlib.sha256).digest()
    return f"{segments}.{_b64url_encode(sig)}"


def verify_jwt_token(token: str) -> dict:
    parts = token.split('.')
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Malformed JWT token")
    header_b64, payload_b64, sig_b64 = parts

    signing_input = f"{header_b64}.{payload_b64}".encode('ascii')
    expected_sig = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()

    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token encoding")

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(status_code=401, detail="Invalid JWT token signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT payload")

    if payload.get("exp") and payload["exp"] < time.time():
        raise HTTPException(status_code=401, detail="JWT token has expired")

    return payload


# Generate default pre-seeded tokens for each persona
PERSONA_TOKENS = {
    key: create_jwt_token(p) for key, p in PERSONAS.items()
}


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI dependency to extract verified persona from Bearer token."""
    if not authorization:
        # Default to Public persona when unauthenticated
        return PERSONAS["public"]

    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    try:
        return verify_jwt_token(token)
    except HTTPException:
        # Fallback to Public if invalid
        return PERSONAS["public"]


def require_roles(allowed_roles: list[str]):
    """FastAPI dependency factory enforcing RBAC."""
    def rbac_dependency(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "Public")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: role '{user_role}' not authorized. Required: {allowed_roles}"
            )
        return user
    return rbac_dependency
