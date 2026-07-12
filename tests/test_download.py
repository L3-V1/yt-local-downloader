from src.services.download import (
    DownloadPreferences,
    DownloadProcessResult,
    SOCKET_TIMEOUT_SECONDS,
    _build_download_attempts,
    _build_initial_response_timeout_message,
    _is_last_attempt,
    DownloadRequestError,
    _build_download_command,
    _compact_process_message,
    _format_download_error,
    _indicates_download_progress,
    _parse_progress_line,
    _log_download_failure,
    _build_preference_args,
    _run_download_job,
    _should_try_fallback,
    _validate_download_preferences,
    _validate_youtube_url,
)
from src.controllers.downloads import (
    get_downloads_status,
    handle_download_video_async,
    handle_retry_download,
    submit_download_video,
)


def test_validate_youtube_url_accepts_public_watch_url():
    url = _validate_youtube_url("https://www.youtube.com/watch?v=abc123")
    assert url == "https://www.youtube.com/watch?v=abc123"


def test_validate_youtube_url_rejects_other_domains():
    try:
        _validate_youtube_url("https://example.com/video")
    except DownloadRequestError as exc:
        assert "YouTube" in str(exc)
    else:
        raise AssertionError("DownloadRequestError was expected")


def test_validate_download_preferences_accepts_supported_values():
    preferences = _validate_download_preferences("webm", "720")

    assert preferences == DownloadPreferences(video_format="webm", video_quality="720")


def test_validate_download_preferences_rejects_invalid_format():
    try:
        _validate_download_preferences("avi", "720")
    except DownloadRequestError as exc:
        assert "formato" in str(exc).lower()
    else:
        raise AssertionError("DownloadRequestError was expected")


def test_compact_process_message_reduces_newlines():
    message = _compact_process_message("line 1\n\nline 2\n")
    assert message == "line 1 line 2"


def test_build_download_command_uses_python_module_invocation():
    command = _build_download_command("https://www.youtube.com/watch?v=abc123")
    assert command[1:3] == ["-m", "yt_dlp"]
    assert "--socket-timeout" in command
    assert "--http-chunk-size" not in command
    assert "--merge-output-format" in command
    assert command[command.index("--merge-output-format") + 1] == "mp4"
    timeout_value = command[command.index("--socket-timeout") + 1]
    assert timeout_value == str(SOCKET_TIMEOUT_SECONDS) == "10"
    assert command[command.index("--retries") + 1] == "6"
    assert "--retry-sleep" in command
    assert command[-1] == "https://www.youtube.com/watch?v=abc123"


def test_build_download_command_adds_runtime_when_available(monkeypatch):
    monkeypatch.setattr("src.services.download.get_preferred_js_runtime", lambda: "node")
    command = _build_download_command("https://www.youtube.com/watch?v=abc123")
    assert "--js-runtimes" in command
    assert "node" in command
    assert "--remote-components" in command


def test_format_download_error_returns_friendly_timeout_message():
    failure = _format_download_error("ERROR: WinError 10060 timed out")
    assert failure.error_type == "timeout_conexao"
    assert "10 segundos sem resposta" in failure.message


def test_format_download_error_returns_sabr_message():
    failure = _format_download_error(
        "WARNING: [youtube] abc: Some android client https formats have been skipped as they are missing a URL. "
        "YouTube may have enabled the SABR-only streaming experiment for the current session."
    )
    assert failure.error_type == "sabr"
    assert "formatos SABR" in failure.message


def test_format_download_error_returns_http_403_message():
    failure = _format_download_error("ERROR: [download] Got error: HTTP Error 403: Forbidden")
    assert failure.error_type == "http_403"
    assert "recusou o fluxo de mídia" in failure.message


def test_should_try_fallback_for_timeout_message():
    assert _should_try_fallback("A conexao com o YouTube expirou durante o download.") is True


def test_should_try_fallback_for_sabr_message():
    assert _should_try_fallback("YouTube may have enabled the SABR-only streaming experiment.") is True


def test_should_try_fallback_for_friendly_http_403_message():
    assert (
        _should_try_fallback(
            "O YouTube recusou o fluxo de mídia deste vídeo durante a transferência."
        )
        is True
    )


def test_build_download_attempts_includes_fallback_profiles():
    attempts = _build_download_attempts()
    labels = [attempt.label for attempt in attempts]
    assert labels == [
        "default_resilient",
        "android_ipv4_progressive",
        "ios_ipv4_progressive",
        "ios_ipv4_hls",
        "conservative_small_chunks",
        "audio_safe_fallback",
    ]


def test_is_last_attempt_only_returns_true_for_final_fallback():
    attempts = _build_download_attempts()

    assert _is_last_attempt(attempts[0]) is False
    assert _is_last_attempt(attempts[-1]) is True


def test_build_download_command_applies_attempt_network_overrides():
    attempts = _build_download_attempts()
    conservative_attempt = next(attempt for attempt in attempts if attempt.label == "conservative_small_chunks")
    command = _build_download_command("https://www.youtube.com/watch?v=abc123", conservative_attempt)

    assert "--force-ipv4" in command
    assert "--http-chunk-size" in command
    assert command[command.index("--http-chunk-size") + 1] == "512K"
    assert command[command.index("--retries") + 1] == "8"
    assert command[command.index("--fragment-retries") + 1] == "8"
    assert command[-1] == "https://www.youtube.com/watch?v=abc123"


def test_build_download_command_applies_ios_hls_fallback_before_url():
    attempts = _build_download_attempts()
    ios_hls_attempt = next(attempt for attempt in attempts if attempt.label == "ios_ipv4_hls")
    command = _build_download_command("https://www.youtube.com/watch?v=abc123", ios_hls_attempt)

    extractor_index = command.index("--extractor-args")
    format_index = command.index("-f")

    assert command[extractor_index + 1] == "youtube:player_client=ios"
    assert "m3u8" in command[format_index + 1]
    assert format_index < len(command) - 1
    assert command[-1] == "https://www.youtube.com/watch?v=abc123"


def test_build_preference_args_supports_original_format_without_remux():
    args = _build_preference_args(DownloadPreferences(video_format="original", video_quality="1080"))

    assert args == ["-S", "res:1080"]


def test_build_download_command_applies_requested_webm_preferences():
    preferences = DownloadPreferences(video_format="webm", video_quality="480")
    command = _build_download_command("https://www.youtube.com/watch?v=abc123", preferences=preferences)

    assert command[command.index("-S") + 1] == "ext:webm,res:480"
    assert command[command.index("--merge-output-format") + 1] == "webm"
    assert command[command.index("--remux-video") + 1] == "webm"


def test_indicates_download_progress_detects_percentage_output():
    assert _indicates_download_progress("[download]  12.4% of 15.30MiB at 1.20MiB/s ETA 00:03") is True


def test_parse_progress_line_extracts_percent_speed_and_eta():
    snapshot = _parse_progress_line("[download]  12.4% of 15.30MiB at 1.20MiB/s ETA 00:03")

    assert snapshot is not None
    assert snapshot.percent == 12.4
    assert snapshot.speed_text == "1.20MiB/s"
    assert snapshot.eta_text == "00:03"
    assert snapshot.progress_text == "12.4% de 15.30MiB"


def test_indicates_download_progress_ignores_extractor_logs():
    assert _indicates_download_progress("[youtube] Extracting URL: https://www.youtube.com/watch?v=abc123") is False


def test_initial_response_timeout_message_mentions_10_seconds():
    assert "10 segundos" in _build_initial_response_timeout_message()


def test_log_download_failure_sends_structured_payload(monkeypatch):
    captured = {}

    def fake_add_application_log(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("src.services.download.add_application_log", fake_add_application_log)

    _log_download_failure(
        download_id="download-1",
        video_url="https://www.youtube.com/watch?v=abc123",
        error_type="timeout_conexao",
        message="A conexão com o YouTube ficou 10 segundos sem resposta durante o download.",
        details="Tentativa: default_resilient",
    )

    assert captured["level"] == "error"
    assert captured["source"] == "downloads"
    assert captured["reference_id"] == "download-1"
    assert "timeout_conexao" in captured["details"]
    assert "default_resilient" in captured["details"]


def test_download_registry_remove_returns_true_for_existing_item():
    from datetime import datetime

    from src.services.download import DownloadItem, DownloadRegistry

    registry = DownloadRegistry()
    registry.add(
        DownloadItem(
            id="download-1",
            video_url="https://www.youtube.com/watch?v=abc123",
            status="Em andamento",
            created_at=datetime.now(),
            video_format="mp4",
            video_quality="best",
        )
    )

    assert registry.remove("download-1") is True
    assert registry.list_downloads() == []


def test_download_registry_remove_returns_false_for_missing_item():
    from src.services.download import DownloadRegistry

    registry = DownloadRegistry()
    assert registry.remove("missing-id") is False


def test_download_registry_clear_removes_all_items():
    from datetime import datetime

    from src.services.download import DownloadItem, DownloadRegistry

    registry = DownloadRegistry()
    registry.add(
        DownloadItem(
            id="download-1",
            video_url="https://www.youtube.com/watch?v=abc123",
            status="Em andamento",
            created_at=datetime.now(),
            video_format="mp4",
            video_quality="best",
        )
    )
    registry.clear()
    assert registry.list_downloads() == []


def test_submit_download_video_returns_success_payload(monkeypatch):
    from fastapi import BackgroundTasks

    monkeypatch.setattr("src.controllers.downloads.enqueue_download", lambda **kwargs: "download-123")

    result = submit_download_video(
        BackgroundTasks(),
        video_url="https://www.youtube.com/watch?v=abc123",
        video_format="mp4",
        video_quality="best",
    )

    assert result.success is True
    assert result.level == "success"
    assert result.download_id == "download-123"
    assert "fila de processamento" in result.message


def test_submit_download_video_returns_error_payload(monkeypatch):
    from fastapi import BackgroundTasks

    def raise_request_error(**kwargs):
        raise DownloadRequestError("invalid")

    monkeypatch.setattr("src.controllers.downloads.enqueue_download", raise_request_error)

    result = submit_download_video(
        BackgroundTasks(),
        video_url="https://example.com/video",
        video_format="avi",
        video_quality="best",
    )

    assert result.success is False
    assert result.level == "error"
    assert result.download_id is None
    assert "url válida" in result.message.lower()


def test_handle_download_video_async_returns_json_success(monkeypatch):
    from fastapi import BackgroundTasks

    monkeypatch.setattr("src.controllers.downloads.enqueue_download", lambda **kwargs: "download-456")

    response = handle_download_video_async(
        BackgroundTasks(),
        video_url="https://www.youtube.com/watch?v=abc123",
        video_format="mp4",
        video_quality="720",
    )

    assert response.status_code == 200
    assert b'"success":true' in response.body
    assert b'"download_id":"download-456"' in response.body


def test_get_downloads_status_returns_current_registry_payload(monkeypatch):
    from datetime import datetime

    from src.services.download import DownloadItem, DownloadRegistry

    registry = DownloadRegistry()
    registry.add(
        DownloadItem(
            id="download-1",
            video_url="https://www.youtube.com/watch?v=abc123",
            status="Em andamento",
            created_at=datetime.now(),
            video_format="mp4",
            video_quality="best",
            progress_percent=42.5,
            progress_text="42.5% de 10.00MiB",
        )
    )

    monkeypatch.setattr("src.controllers.downloads.download_registry", registry)

    response = get_downloads_status()

    assert response.status_code == 200
    assert b'"downloads"' in response.body
    assert b'"id":"download-1"' in response.body
    assert b'"progress_percent":42.5' in response.body


def test_handle_retry_download_requeues_failed_item(monkeypatch):
    from datetime import datetime

    from fastapi import BackgroundTasks

    from src.services.download import DownloadItem, DownloadRegistry

    registry = DownloadRegistry()
    registry.add(
        DownloadItem(
            id="download-1",
            video_url="https://www.youtube.com/watch?v=abc123",
            status="Erro",
            created_at=datetime.now(),
            video_format="webm",
            video_quality="720",
        )
    )

    monkeypatch.setattr("src.controllers.downloads.download_registry", registry)
    monkeypatch.setattr("src.controllers.downloads.enqueue_retry_download", lambda background_tasks, download_id: "retry-1")

    response = handle_retry_download(BackgroundTasks(), "download-1")

    assert response.status_code == 303
    assert "retry-1" in response.headers["location"]


def test_run_download_job_retries_after_startup_timeout_until_fallback_succeeds(monkeypatch, tmp_path):
    from src.services.download import DownloadItem, DownloadRegistry
    from datetime import datetime

    registry = DownloadRegistry()
    registry.add(
        DownloadItem(
            id="download-1",
            video_url="https://www.youtube.com/watch?v=abc123",
            status="Em andamento",
            created_at=datetime.now(),
            video_format="mp4",
            video_quality="best",
        )
    )

    results = iter(
        [
            DownloadProcessResult(returncode=1, stdout="", stderr="", timed_out_before_progress=True),
            DownloadProcessResult(returncode=0, stdout="[download] Destination: video.mp4", stderr=""),
        ]
    )
    attempted_labels = []

    monkeypatch.setattr("src.services.download.download_registry", registry)
    monkeypatch.setattr("src.services.download.DOWNLOADS_DIR", tmp_path)
    monkeypatch.setattr("src.services.download.build_subprocess_env", lambda: {})
    monkeypatch.setattr(
        "src.services.download._execute_download_process",
        lambda command, env, download_id: next(results),
    )
    monkeypatch.setattr(
        "src.services.download._build_download_command",
        lambda video_url, attempt, preferences: attempted_labels.append(attempt.label) or [attempt.label],
    )
    monkeypatch.setattr("src.services.download._log_download_failure", lambda **kwargs: None)

    _run_download_job(
        "download-1",
        "https://www.youtube.com/watch?v=abc123",
        DownloadPreferences(video_format="mp4", video_quality="best"),
    )

    download_item = registry.list_downloads()[0]
    assert attempted_labels[:2] == ["default_resilient", "android_ipv4_progressive"]
    assert download_item.status == "Concluido"
    assert download_item.file_name == "video.mp4"


def test_run_download_job_logs_all_tested_profiles_on_final_failure(monkeypatch, tmp_path):
    from datetime import datetime

    from src.services.download import DownloadItem, DownloadRegistry

    registry = DownloadRegistry()
    registry.add(
        DownloadItem(
            id="download-1",
            video_url="https://www.youtube.com/watch?v=abc123",
            status="Em andamento",
            created_at=datetime.now(),
            video_format="mp4",
            video_quality="best",
        )
    )

    captured_log = {}

    monkeypatch.setattr("src.services.download.download_registry", registry)
    monkeypatch.setattr("src.services.download.DOWNLOADS_DIR", tmp_path)
    monkeypatch.setattr("src.services.download.build_subprocess_env", lambda: {})
    monkeypatch.setattr(
        "src.services.download._execute_download_process",
        lambda command, env, download_id: DownloadProcessResult(
            returncode=1,
            stdout="",
            stderr="ERROR: [download] Got error: HTTP Error 403: Forbidden",
        ),
    )
    monkeypatch.setattr(
        "src.services.download._log_download_failure",
        lambda **kwargs: captured_log.update(kwargs),
    )

    _run_download_job(
        "download-1",
        "https://www.youtube.com/watch?v=abc123",
        DownloadPreferences(video_format="mp4", video_quality="best"),
    )

    assert captured_log["error_type"] == "http_403"
    assert "Perfis testados:" in captured_log["details"]
    assert "audio_safe_fallback" in captured_log["details"]
