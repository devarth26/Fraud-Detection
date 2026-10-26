"""Load policy documents, attach metadata, chunk them and build a vector store."""
from __future__ import annotations

import re
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

DEFAULT_POLICY_DIR = Path(__file__).resolve().parent.parent / "policies"

_ID_RE = re.compile(r"^(?:Policy|Case) ID:\s*([A-Z]+-\d{3})\s*$", re.MULTILINE)
_RULES_RE = re.compile(r"^Applies to rules:\s*(.+)$", re.MULTILINE)
_PERSONAS_RE = re.compile(r"^Applies to personas:\s*(.+)$", re.MULTILINE)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _parse_list(match: re.Match | None) -> list[str]:
    if not match:
        return []
    items = [x.strip() for x in match.group(1).split(",")]
    return [x for x in items if x and x.lower() not in {"none", "all"}]


def load_documents(policy_dir: Path | str = DEFAULT_POLICY_DIR) -> list[Document]:
    """Load .md/.txt/.pdf files (recursively) and attach doc-level metadata."""
    policy_dir = Path(policy_dir)
    docs: list[Document] = []
    for path in sorted(policy_dir.rglob("*")):
        if path.suffix.lower() in {".md", ".txt"}:
            loaded = TextLoader(str(path), encoding="utf-8").load()
        elif path.suffix.lower() == ".pdf":
            loaded = PyPDFLoader(str(path)).load()
        else:
            continue
        text = "\n".join(d.page_content for d in loaded)
        id_match = _ID_RE.search(text)
        title_match = _TITLE_RE.search(text)
        doc_id = id_match.group(1) if id_match else path.stem.split("_")[0]
        meta = {
            "source": str(path.relative_to(policy_dir)),
            "doc_id": doc_id,
            "doc_type": "case" if doc_id.startswith("CASE") else "policy",
            "title": title_match.group(1).strip() if title_match else path.stem,
            "rule_codes": _parse_list(_RULES_RE.search(text)),
            "personas": _parse_list(_PERSONAS_RE.search(text)),
        }
        docs.append(Document(page_content=text, metadata=meta))
    if not docs:
        raise FileNotFoundError(f"No policy documents found in {policy_dir}")
    return docs


def chunk_documents(docs: list[Document], chunk_size: int = 700, overlap: int = 80) -> list[Document]:
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "section")], strip_headers=False
    )
    char_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    chunks: list[Document] = []
    for doc in docs:
        for section_doc in header_splitter.split_text(doc.page_content):
            for piece in char_splitter.split_text(section_doc.page_content):
                meta = {**doc.metadata, "section": section_doc.metadata.get("section", "Overview")}
                # Prefix with the id/title so each chunk is self-describing when embedded.
                text = f"[{meta['doc_id']}] {meta['title']}\n{piece}"
                chunks.append(Document(page_content=text, metadata=meta))
    return chunks


def build_vector_store(
    embeddings: Embeddings, policy_dir: Path | str = DEFAULT_POLICY_DIR
) -> InMemoryVectorStore:
    chunks = chunk_documents(load_documents(policy_dir))
    store = InMemoryVectorStore(embedding=embeddings)
    store.add_documents(chunks)
    return store
