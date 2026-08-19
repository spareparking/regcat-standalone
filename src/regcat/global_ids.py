"""Global identity for cross-doc references.

A doc has its own local namespace for span_ids (S0001, S0002, ...) and
req_ids (R00001, R00002, ...). For cross-doc relationships we need a global
namespace; the convention is `<doc_id>:<local_id>`:

    fda/21-cfr-part-11:S0042
    fda/21-cfr-part-50:R00017

Per-doc JSONL files (spans.jsonl, requirements.jsonl, relationships.jsonl) keep
local IDs — that's stable, append-friendly, and round-trippable. Cross-doc
artifacts (docs/cross_doc_relationships.jsonl) use global IDs.
"""
from __future__ import annotations


def global_id(doc_id: str, local_id: str) -> str:
    """Compose a doc_id and a local id into a global id."""
    return f"{doc_id}:{local_id}"


def split_global_id(g: str) -> tuple[str, str]:
    """Inverse of global_id. Returns (doc_id, local_id)."""
    # doc_id may contain a single '/' (e.g. fda/21-cfr-part-11), and the
    # local id is everything after the LAST ':' (R-ids never contain ':').
    if ":" not in g:
        raise ValueError(f"not a global id: {g!r}")
    doc_id, _, local = g.rpartition(":")
    return doc_id, local


def is_global_id(s: str) -> bool:
    return ":" in s
