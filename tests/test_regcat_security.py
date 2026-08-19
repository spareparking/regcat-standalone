from __future__ import annotations

import pytest

from regcat.agent_packets import packet_dir
from regcat.registry import parse_doc_id


def test_doc_id_rejects_path_traversal() -> None:
    for doc_id in ("fda/../secret", "../fda/part-11", "fda/part/11", "fda/.hidden"):
        with pytest.raises(ValueError):
            parse_doc_id(doc_id)


def test_packet_batch_id_rejects_path_traversal(tmp_path) -> None:
    with pytest.raises(ValueError):
        packet_dir(tmp_path, "fda/part-11", "classify", "../escape")
    with pytest.raises(ValueError):
        packet_dir(tmp_path, "fda/part-11", "../classify", "batch-1")
