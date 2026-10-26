import pytest

from rag.s3 import sync_policies_from_s3


class FakeS3:
    def __init__(self, keys):
        self.keys, self.downloads = keys, []

    def get_paginator(self, name):
        keys = self.keys

        class P:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": k} for k in keys if k.startswith(Prefix)]}
        return P()

    def download_file(self, bucket, key, target):
        from pathlib import Path
        Path(target).write_text(f"# {key}")
        self.downloads.append(key)


def test_downloads_only_policy_files_and_skips_traversal(tmp_path):
    s3 = FakeS3(["policies/POL-001.md", "policies/notes.txt", "policies/image.png", "policies/../../evil.md", "policies/"])
    got = sync_policies_from_s3("b", "policies/", tmp_path, client=s3)
    assert sorted(got) == ["POL-001.md", "notes.txt"]
    assert (tmp_path / "POL-001.md").exists() and not (tmp_path.parent / "evil.md").exists()


def test_empty_prefix_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        sync_policies_from_s3("b", "policies/", tmp_path, client=FakeS3([]))
