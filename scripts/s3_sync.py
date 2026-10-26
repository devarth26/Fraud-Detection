"""Upload local policy documents to S3 (so the running service can pick up policy edits).

    python scripts/s3_sync.py --bucket my-fraudshield-docs [--prefix policies/]
Then restart the ECS service; the retriever re-reads S3 on startup when POLICY_S3_BUCKET is set.
"""
import argparse
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--prefix", default="policies/")
    ap.add_argument("--dir", default=str(ROOT / "policies"))
    args = ap.parse_args()
    s3 = boto3.client("s3")
    base = Path(args.dir)
    count = 0
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".pdf"}:
            key = args.prefix + path.relative_to(base).as_posix()
            s3.upload_file(str(path), args.bucket, key)
            print(f"uploaded {path.name} -> s3://{args.bucket}/{key}")
            count += 1
    print(f"{count} files uploaded")


if __name__ == "__main__":
    main()
