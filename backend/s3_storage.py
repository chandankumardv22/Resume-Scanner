# ==============================================================================
# TECH STACK: [Amazon Web Services (AWS) - Amazon S3 Client]
# Optional Persistent Object Storage with Server-Side Encryption and Presigned URLs
# ==============================================================================
from __future__ import annotations

import os
from typing import Any

from logger import logger

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None
    Config = None
    BotoCoreError = Exception
    ClientError = Exception

_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "").strip()
_AWS_REGION = os.getenv("AWS_REGION", "ap-south-1").strip()
_DEFAULT_URL_EXPIRY_SECONDS = int(os.getenv("S3_PRESIGNED_URL_EXPIRES_SEC", "900"))  # 15 minutes

_s3_client: Any = None

if boto3 is not None and _BUCKET_NAME:
    try:
        _s3_client = boto3.client(
            "s3",
            region_name=_AWS_REGION,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
        )
        logger.info(f"[S3] Initialized Amazon S3 client targeting bucket '{_BUCKET_NAME}' in {_AWS_REGION}")
    except Exception as exc:
        logger.warning(f"[S3] Could not initialize boto3 S3 client: {exc}")
        _s3_client = None


def is_s3_enabled() -> bool:
    """Returns True if Amazon S3 persistent storage is configured and available."""
    return _s3_client is not None and bool(_BUCKET_NAME)


def upload_resume_or_report(
    file_bytes: bytes,
    object_key: str,
    content_type: str = "application/pdf",
    metadata: dict[str, str] | None = None,
) -> str | None:
    """
    Uploads document bytes to S3 with AES-256 Server-Side Encryption and private ACL.
    Returns the object key if successful, or None if S3 is not enabled or upload fails.
    """
    if not is_s3_enabled():
        return None

    try:
        clean_meta = {k: str(v) for k, v in (metadata or {}).items()}
        _s3_client.put_object(
            Bucket=_BUCKET_NAME,
            Key=object_key,
            Body=file_bytes,
            ContentType=content_type,
            ServerSideEncryption="AES256",
            Metadata=clean_meta,
        )
        logger.info(f"[S3] Securely uploaded object to s3://{_BUCKET_NAME}/{object_key}")
        return object_key
    except Exception as exc:
        logger.error(f"[S3] Failed to upload object '{object_key}': {exc}")
        return None


def generate_presigned_download_url(
    object_key: str,
    expiration_sec: int = _DEFAULT_URL_EXPIRY_SECONDS,
) -> str | None:
    """
    Generates a short-lived (default 15-min) secure presigned URL for private S3 objects.
    Ensures zero public S3 bucket exposure while allowing authorized candidate downloads.
    """
    if not is_s3_enabled():
        return None

    try:
        url = _s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": _BUCKET_NAME, "Key": object_key},
            ExpiresIn=expiration_sec,
        )
        return url
    except Exception as exc:
        logger.error(f"[S3] Error generating presigned URL for '{object_key}': {exc}")
        return None


def delete_object(object_key: str) -> bool:
    """Deletes an object from the configured S3 bucket."""
    if not is_s3_enabled():
        return False
    try:
        _s3_client.delete_object(Bucket=_BUCKET_NAME, Key=object_key)
        return True
    except Exception as exc:
        logger.error(f"[S3] Failed to delete object '{object_key}': {exc}")
        return False
