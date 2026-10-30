"""Optional: pull policy documents from S3 so policies can be updated without rebuilding the image."""
from __future__ import annotations

from pathlib import Path

ALLOWED_SUFFIXES = {".md", ".txt", ".pdf"}


def sync_policies_from_s3(bucket: str, prefix: str, dest: Path | str, client=None) -> list[str]:
    """Download every policy file under s3://bucket/prefix into dest. Returns local relative paths."""
    if client is None:
        import boto3

        client = boto3.client("s3")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    downloaded: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rel = key[len(prefix):].lstrip("/")
            if not rel or Path(rel).suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            target = (dest / rel).resolve()
            if dest.resolve() not in target.parents:  # refuse keys like "../../x"
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(target))
            downloaded.append(rel)
    if not downloaded:
        raise FileNotFoundError(f"No policy files found at s3://{bucket}/{prefix}")
    return downloaded
