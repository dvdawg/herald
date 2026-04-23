from src.web.schemas import RunRequest
from src.web.service import HeraldWebService


class _FakePipeline:
    def search_and_rank(
        self,
        query,
        max_results=None,
        weights=None,
        process_metadata=None,
        process_text=None,
        date_from=None,
        date_to=None,
    ):
        return [
            (
                {
                    "title": "Paper A",
                    "authors": [{"full_name": "Alice"}, {"full_name": "Bob"}],
                    "published": "2025-01-01T00:00:00+00:00",
                    "abstract": "A summary",
                    "pdf_url": "https://example.com/a.pdf",
                    "citation_count": 3,
                    "arxiv_id": "2501.00001",
                    "ranking_features": {"relevance": 0.9, "recency": 0.5},
                    "ranking_explanation": ["High semantic similarity to the query."],
                },
                0.9,
            ),
            (
                {
                    "title": "Paper B",
                    "authors": ["Carol"],
                },
                0.6,
            ),
        ]


def test_web_service_normalizes_pipeline_output():
    service = HeraldWebService(pipeline=_FakePipeline())
    payload = RunRequest(query="quantum", max_results=10, top_k=1)

    response = service.run(payload)

    assert response.status == "ok"
    assert response.query == "quantum"
    assert response.debug.total_results == 2
    assert response.debug.returned_results == 1
    assert response.results[0].title == "Paper A"
    assert response.results[0].authors == ["Alice", "Bob"]
    assert response.results[0].rank == 1
    assert response.results[0].score == 0.9
    assert response.results[0].ranking_features == {"relevance": 0.9, "recency": 0.5}
    assert response.results[0].ranking_explanation == ["High semantic similarity to the query."]
