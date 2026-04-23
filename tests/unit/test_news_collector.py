import datetime as dt

from src.data_collectors.news_collector import NewsCollector


def test_parse_feed_supports_rss_and_atom():
    collector = NewsCollector()

    rss_xml = """
    <rss version="2.0">
      <channel>
        <item>
          <title>RSS item</title>
          <link>https://example.com/rss</link>
          <description>Summary</description>
          <pubDate>Mon, 30 Mar 2026 12:00:00 GMT</pubDate>
          <author>rss-author</author>
          <category>ai</category>
        </item>
      </channel>
    </rss>
    """
    atom_xml = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Atom item</title>
        <link href="https://example.com/atom" />
        <summary>Atom summary</summary>
        <updated>2026-03-30T13:00:00Z</updated>
        <author><name>atom-author</name></author>
        <category term="ml" />
      </entry>
    </feed>
    """

    rss_items = collector._parse_feed(rss_xml, default_source="rss", default_label="RSS")
    atom_items = collector._parse_feed(atom_xml, default_source="atom", default_label="Atom")

    assert rss_items[0]["title"] == "RSS item"
    assert rss_items[0]["tags"] == ["ai"]
    assert atom_items[0]["url"] == "https://example.com/atom"
    assert atom_items[0]["author"] == "atom-author"
    assert atom_items[0]["tags"] == ["ml"]


def test_parse_feed_uses_url_guid_when_link_is_missing():
    collector = NewsCollector()

    rss_xml = """
    <rss version="2.0">
      <channel>
        <item>
          <title>RSS guid item</title>
          <guid>https://example.com/guid-item</guid>
          <pubDate>Mon, 30 Mar 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    items = collector._parse_feed(rss_xml, default_source="rss", default_label="RSS")

    assert items[0]["url"] == "https://example.com/guid-item"


def test_parse_anthropic_news_page_extracts_news_cards():
    collector = NewsCollector()

    html = """
    <html>
      <body>
        <a href="/news/model-card">
          Announcements Apr 8, 2026 Claude model card
        </a>
        <a href="https://www.anthropic.com/news/research-note">
          Research Mar 28, 2026 New alignment note
        </a>
        <a href="/news">News index</a>
      </body>
    </html>
    """

    items = collector._parse_anthropic_news_page(html)

    assert [item["title"] for item in items] == ["Claude model card", "New alignment note"]
    assert items[0]["published"] == "Apr 8, 2026"
    assert items[0]["source"] == "anthropic-news"


def test_collect_ranks_and_reports_unavailable_sources():
    class _StubCollector(NewsCollector):
        def __init__(self):
            pass

        def _fetch_hackernews(self, query, hours_back):
            recent = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
            return [
                {
                    "title": "LLM launch",
                    "summary": "New model ships",
                    "url": "https://example.com/launch",
                    "published": recent,
                    "author": "author",
                    "source": "hackernews",
                    "source_label": "Hacker News",
                    "score_points": 80,
                    "comment_count": 20,
                    "tags": ["llm"],
                    "raw_item": {},
                }
            ]

    collector = _StubCollector()

    items, unavailable_sources, source_counts = collector.collect(
        query="llm",
        sources=["hackernews", "missing-source"],
        limit=10,
        hours_back=24,
    )

    assert len(items) == 1
    assert items[0]["score"] > 0
    assert unavailable_sources == ["missing-source"]
    assert source_counts == {"hackernews": 1}


def test_default_sources_cover_all_news_sources():
    collector = NewsCollector()

    assert set(collector.default_sources) == set(NewsCollector.ALL_SOURCE_IDS)


def test_blank_query_scores_overall_importance_over_raw_recency():
    collector = NewsCollector()
    now = dt.datetime.now(dt.timezone.utc)
    important = {
        "title": "OpenAI launches frontier model with new safety policy",
        "summary": "",
        "published": (now - dt.timedelta(hours=12)).isoformat(),
        "source": "openai-news",
        "tags": [],
    }
    routine = {
        "title": "Small library update",
        "summary": "",
        "published": (now - dt.timedelta(hours=1)).isoformat(),
        "source": "lobsters",
        "tags": [],
    }

    collector._annotate_cross_source_signals([important, routine])

    assert collector._score_item(important, query="") > collector._score_item(routine, query="")


def test_cross_source_overlap_boosts_related_stories():
    collector = NewsCollector()
    items = [
        {"title": "OpenAI launches GPT model", "source": "openai-news"},
        {"title": "OpenAI releases GPT model", "source": "hackernews"},
        {"title": "NVIDIA posts developer guide", "source": "nvidia-developer"},
    ]

    collector._annotate_cross_source_signals(items)

    assert items[0]["cross_source_count"] == 1
    assert items[1]["cross_source_count"] == 1
    assert items[2]["cross_source_count"] == 0
