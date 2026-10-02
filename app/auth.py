"""Device-token auth for the Sentinel ingest API.

Agents authenticate with a Bearer token issued at /register. We store only the
token's SHA-256 hash, never the token itself. /register is gated by a shared
enrollment secret delivered to agents by MDM.
"""
import hashlib
import os
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import database, models


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_enrollment(x_enrollment_secret: str = Header(None)) -> None:
    """Gate /register with the MDM-delivered enrollment secret."""
    expected = os.getenv("ENROLLMENT_SECRET")
    if not expected or not x_enrollment_secret or not secrets.compare_digest(
        x_enrollment_secret, expected
    ):
        raise HTTPException(status_code=401, detail="Invalid enrollment secret")


def require_device(
    authorization: str = Header(None), db: Session = Depends(get_db)
) -> models.STDevice:
    """Resolve the device from its Bearer token, or 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing device token")
    token_hash = hash_token(authorization[len("Bearer "):])
    device = (
        db.query(models.STDevice)
        .filter(models.STDevice.st_token_hash == token_hash)
        .first()
    )
    if not device:
        raise HTTPException(status_code=401, detail="Invalid device token")
    return device


def require_same_device(device: models.STDevice, claimed_device_id: str) -> None:
    """Stop one enrolled device from writing data as another."""
    if claimed_device_id != device.st_device_id:
        raise HTTPException(status_code=403, detail="Token does not match device")


if __name__ == "__main__":
    # ponytail: self-check for the security-critical bits, no framework
    a, b = generate_token(), generate_token()
    assert a != b, "tokens must be unique"
    assert hash_token(a) == hash_token(a), "hash must be stable"
    assert hash_token(a) != hash_token(b), "different tokens, different hashes"
    assert len(hash_token(a)) == 64, "sha-256 hex is 64 chars"
    assert secrets.compare_digest(hash_token(a), hash_token(a))
    print("auth self-check OK")
