from src.web.news_service import HeraldNewsService
from src.web.schemas import NewsRequest


class _FakeNewsCollector:
    def collect(self, query="", sources=None, limit=20, hours_back=72):
        return (
            [
                {
                    "title": "OpenAI releases something new",
                    "summary": "A short summary",
                    "url": "https://example.com/story",
                    "source": "hackernews",
                    "source_label": "Hacker News",
                    "author": "pg",
                    "published": "2026-03-30T12:00:00+00:00",
                    "tags": ["ai", "release"],
                    "score_points": 123,
                    "comment_count": 45,
                    "score": 0.91,
                    "raw_item": {"id": "abc"},
                }
            ],
            ["x"],
            {"hackernews": 1, "lobsters": 0},
        )


def test_news_service_normalizes_collector_output():
    service = HeraldNewsService(collector=_FakeNewsCollector())
    payload = NewsRequest(query="openai", limit=5, hours_back=24, sources=["hackernews", "x"])

    response = service.run(payload)

    assert response.status == "ok"
    assert response.query == "openai"
    assert response.debug.total_candidates == 1
    assert response.debug.returned_results == 1
    assert response.debug.unavailable_sources == ["x"]
    assert response.results[0].rank == 1
    assert response.results[0].source_label == "Hacker News"
    assert response.results[0].score_points == 123
    assert response.results[0].comment_count == 45

