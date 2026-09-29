from engine.models import RawItem, Relevance


def test_raw_item_minimal():
    item = RawItem(id="abc", source="csv", source_id="1", text="hello world " * 5)
    assert item.source == "csv"


def test_relevance_bounds():
    r = Relevance(
        id="x",
        is_retrieval_related=True,
        is_vague_memory=True,
        confidence=0.9,
        reason="find old photo",
    )
    assert r.confidence == 0.9
