from rag.embeddings import HashingEmbeddings
from rag.ingest import chunk_documents, load_documents
from rag.retriever import PolicyRetriever

from .fakes import get_test_retriever


def test_loads_ten_policies_and_three_cases():
    docs = load_documents()
    ids = {d.metadata["doc_id"] for d in docs}
    assert {f"POL-{i:03d}" for i in range(1, 11)} <= ids
    assert {d.metadata["doc_id"] for d in docs if d.metadata["doc_type"] == "case"} == {"CASE-001", "CASE-002", "CASE-003"}


def test_metadata_parsed_from_headers():
    pol1 = next(d for d in load_documents() if d.metadata["doc_id"] == "POL-001")
    assert "MICRO_TRANSACTION_CARD_TEST" in pol1.metadata["rule_codes"]
    assert "CARD_TESTING" in pol1.metadata["personas"]
    pol10 = next(d for d in load_documents() if d.metadata["doc_id"] == "POL-010")
    assert pol10.metadata["rule_codes"] == []  # "all" means no specific rule codes


def test_chunks_are_self_describing_and_keep_metadata():
    chunks = chunk_documents(load_documents())
    assert len(chunks) > 30
    assert all(c.page_content.startswith(f"[{c.metadata['doc_id']}]") for c in chunks)
    assert all(c.metadata["section"] for c in chunks)


def test_card_testing_query_returns_pol001_first():
    hits = get_test_retriever().search(
        "burst of micro transactions on a new card",
        k=3, rule_codes=["MICRO_TRANSACTION_CARD_TEST", "VELOCITY_SPIKE_CRITICAL"], personas=["CARD_TESTING"],
    )
    assert hits[0]["doc_id"] == "POL-001"
    assert "MICRO_TRANSACTION_CARD_TEST" in hits[0]["matched_rules"]


def test_account_takeover_query_surfaces_ato_policy_in_top_two():
    hits = get_test_retriever().search(
        "new device vpn high-risk country", k=3,
        rule_codes=["TRIPLE_THREAT_VPN_LOCATION_DEVICE"], personas=["ACCOUNT_TAKEOVER"],
    )
    assert "POL-002" in [h["doc_id"] for h in hits[:2]]


def test_human_review_question_returns_escalation_policy():
    hits = get_test_retriever().search("when does a case need human review and what is the service level", k=3)
    assert hits[0]["doc_id"] == "POL-010"


def test_one_result_per_document_and_cases_can_be_excluded():
    r = get_test_retriever()
    hits = r.search("micro transactions card testing", k=6)
    ids = [h["doc_id"] for h in hits]
    assert len(ids) == len(set(ids))
    assert not any(h["doc_type"] == "case" for h in r.search("card testing burst", k=6, include_cases=False))


def test_rule_boost_changes_ranking():
    r = PolicyRetriever.build(embeddings=HashingEmbeddings())
    plain = r.search("transaction review", k=10)
    boosted = r.search("transaction review", k=10, rule_codes=["CRYPTO_NEWCARD_INTERNATIONAL"])
    def rank(hits):
        return [h["doc_id"] for h in hits].index("POL-006")

    assert rank(boosted) < rank(plain)
