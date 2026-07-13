from src.services.search import (
    PAGE_SIZE,
    SearchServiceError,
    _is_supported_youtube_url,
    _normalize_entries,
    search_videos,
)


class DummyYoutubeDL:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, query, download):
        assert query == "ytsearch11:python fastapi"
        assert download is False
        return {
            "entries": [
                {
                    "id": "abc123",
                    "title": "FastAPI Tutorial",
                    "channel": "Open Channel",
                    "duration": 125,
                },
                {
                    "id": "def456",
                    "title": "FastAPI Course",
                    "channel": "Dev Channel",
                    "duration_string": "01:30:00",
                },
            ]
        }


class DummyYoutubeDLPagination:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, query, download):
        assert query == "ytsearch21:python fastapi"
        return {
            "entries": [
                {"id": f"id{i}", "title": f"Video {i}", "channel": "Channel"} for i in range(21)
            ]
        }


class DummyYoutubeDLDirectVideo:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, query, download):
        assert query == "https://www.youtube.com/watch?v=abc123"
        assert download is False
        return {
            "id": "abc123",
            "title": "Vídeo direto",
            "channel": "Canal direto",
            "duration": 93,
            "thumbnail": "https://img.youtube.com/direct.jpg",
            "url": "https://www.youtube.com/watch?v=abc123",
        }


def test_search_videos_returns_paginated_entries(monkeypatch):
    monkeypatch.setattr("src.services.search.YoutubeDL", DummyYoutubeDL)

    result = search_videos("python fastapi")

    assert result["items"] == [
        {
            "title": "FastAPI Tutorial",
            "channel": "Open Channel",
            "duration_display": "02:05",
            "url": "https://www.youtube.com/watch?v=abc123",
            "thumbnail": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
        },
        {
            "title": "FastAPI Course",
            "channel": "Dev Channel",
            "duration_display": "01:30:00",
            "url": "https://www.youtube.com/watch?v=def456",
            "thumbnail": "https://i.ytimg.com/vi/def456/hqdefault.jpg",
        },
    ]
    assert result["has_more"] is False
    assert result["page"] == 1
    assert result["page_size"] == PAGE_SIZE


def test_search_videos_supports_second_page(monkeypatch):
    monkeypatch.setattr("src.services.search.YoutubeDL", DummyYoutubeDLPagination)

    result = search_videos("python fastapi", page=2)

    assert len(result["items"]) == 10
    assert result["items"][0]["title"] == "Video 10"
    assert result["has_more"] is True


def test_search_videos_accepts_direct_youtube_url(monkeypatch):
    monkeypatch.setattr("src.services.search.YoutubeDL", DummyYoutubeDLDirectVideo)

    result = search_videos("https://www.youtube.com/watch?v=abc123")

    assert result["items"] == [
        {
            "title": "Vídeo direto",
            "channel": "Canal direto",
            "duration_display": "01:33",
            "url": "https://www.youtube.com/watch?v=abc123",
            "thumbnail": "https://img.youtube.com/direct.jpg",
        }
    ]
    assert result["has_more"] is False
    assert result["page"] == 1


def test_search_videos_rejects_empty_query():
    try:
        search_videos("   ")
    except SearchServiceError as exc:
        assert "Informe um termo" in str(exc)
    else:
        raise AssertionError("SearchServiceError was expected")


def test_normalize_entries_skips_invalid_urls():
    results = _normalize_entries([{"title": "No URL"}])
    assert results == []


def test_normalize_entries_defaults_missing_duration():
    results = _normalize_entries([{"id": "abc123", "title": "Vídeo", "channel": "Canal"}])

    assert results == [
        {
            "title": "Vídeo",
            "channel": "Canal",
            "duration_display": "Não informado",
            "url": "https://www.youtube.com/watch?v=abc123",
            "thumbnail": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
        }
    ]


def test_is_supported_youtube_url_detects_watch_url():
    assert _is_supported_youtube_url("https://www.youtube.com/watch?v=abc123") is True


def test_is_supported_youtube_url_rejects_non_youtube_url():
    assert _is_supported_youtube_url("https://example.com/watch?v=abc123") is False
