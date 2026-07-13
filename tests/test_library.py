from __future__ import annotations

from pathlib import Path
from typing import cast
import zipfile

from fastapi.responses import FileResponse

from src.controllers.library import (
    handle_open_library_video,
    handle_transfer_library_video,
    handle_transfer_library_videos,
    stream_library_video,
)
from src.services.library import (
    LibraryServiceError,
    _build_display_title,
    _build_renamed_file_path,
    build_transfer_archive,
    _delete_resolved_file,
    _format_duration,
    _format_file_size,
    get_video_media_type,
    _normalize_file_names,
    open_video_file,
    _probe_media_metadata,
    _rename_resolved_file,
    _resolve_download_file,
    transfer_video_file,
)


def _make_box(box_type: str, payload: bytes) -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + box_type.encode("ascii") + payload


def _build_minimal_mp4(*, duration_seconds: int, width: int, height: int) -> bytes:
    mvhd_payload = (
        b"\x00\x00\x00\x00"
        + (0).to_bytes(4, "big")
        + (0).to_bytes(4, "big")
        + (1000).to_bytes(4, "big")
        + (duration_seconds * 1000).to_bytes(4, "big")
        + bytes(80)
    )
    tkhd_payload = (
        b"\x00\x00\x00\x07"
        + (0).to_bytes(4, "big")
        + (0).to_bytes(4, "big")
        + (1).to_bytes(4, "big")
        + (0).to_bytes(4, "big")
        + (duration_seconds * 1000).to_bytes(4, "big")
        + bytes(8)
        + bytes(2)
        + bytes(2)
        + bytes(2)
        + bytes(2)
        + bytes(36)
        + (width << 16).to_bytes(4, "big")
        + (height << 16).to_bytes(4, "big")
    )
    hdlr_payload = b"\x00\x00\x00\x00" + (0).to_bytes(4, "big") + b"vide" + bytes(12)
    moov_payload = (
        _make_box("mvhd", mvhd_payload)
        + _make_box("trak", _make_box("tkhd", tkhd_payload) + _make_box("mdia", _make_box("hdlr", hdlr_payload)))
    )
    return _make_box("ftyp", b"isom\x00\x00\x02\x00isom") + _make_box("moov", moov_payload)


def test_format_file_size_returns_human_readable_value():
    assert _format_file_size(2048) == "2.0 KB"


def test_format_duration_formats_minutes_and_seconds():
    assert _format_duration("125.9") == "02:05"


def test_build_display_title_removes_video_id_suffix():
    assert _build_display_title("Meu_video [abc123]") == "Meu video"


def test_resolve_download_file_rejects_path_traversal():
    try:
        _resolve_download_file("../secret.txt")
    except LibraryServiceError as exc:
        assert "inválido" in str(exc).lower()
    else:
        raise AssertionError("LibraryServiceError was expected")


def test_normalize_file_names_rejects_empty_selection():
    try:
        _normalize_file_names(["", "   "])
    except LibraryServiceError as exc:
        assert "selecione pelo menos um vídeo" in str(exc).lower()
    else:
        raise AssertionError("LibraryServiceError was expected")


def test_normalize_file_names_deduplicates_and_preserves_order():
    normalized_names = _normalize_file_names(["a.mp4", "a.mp4", " b.mp4 ", "", "c.mp4"])

    assert normalized_names == ["a.mp4", "b.mp4", "c.mp4"]


def test_open_video_file_returns_resolved_path(monkeypatch, tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("data", encoding="utf-8")
    monkeypatch.setattr("src.services.library._resolve_download_file", lambda _: file_path)

    assert open_video_file("video.mp4") == file_path


def test_transfer_video_file_returns_resolved_path(monkeypatch, tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("data", encoding="utf-8")
    monkeypatch.setattr("src.services.library._resolve_download_file", lambda _: file_path)

    assert transfer_video_file("video.mp4") == file_path


def test_get_video_media_type_returns_known_type(tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("data", encoding="utf-8")

    assert get_video_media_type(file_path) == "video/mp4"


def test_build_transfer_archive_creates_zip_with_selected_files(tmp_path):
    first_file = tmp_path / "video-1.mp4"
    second_file = tmp_path / "video-2.webm"
    first_file.write_text("first", encoding="utf-8")
    second_file.write_text("second", encoding="utf-8")

    archive_path = build_transfer_archive([first_file, second_file])

    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as archive_file:
        assert archive_file.namelist() == ["video-1.mp4", "video-2.webm"]
        assert archive_file.read("video-1.mp4") == b"first"
        assert archive_file.read("video-2.webm") == b"second"
    archive_path.unlink()


def test_probe_media_metadata_falls_back_without_ffprobe(tmp_path, monkeypatch):
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(_build_minimal_mp4(duration_seconds=61, width=1280, height=720))
    monkeypatch.setattr("src.services.library.find_executable", lambda _: None)

    metadata = _probe_media_metadata(file_path)

    assert metadata["duration_display"] == "01:01"
    assert metadata["resolution"] == "1280x720"


def test_handle_open_library_video_redirects_to_media_url(monkeypatch, tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("data", encoding="utf-8")
    monkeypatch.setattr("src.controllers.library.open_video_file", lambda _: file_path)

    response = handle_open_library_video(file_name="video.mp4")

    assert response.status_code == 303
    assert response.headers["location"] == "/library/media?file_name=video.mp4"


def test_stream_library_video_serves_file(monkeypatch, tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(b"video-data")
    monkeypatch.setattr("src.controllers.library.open_video_file", lambda _: file_path)

    response = cast(FileResponse, stream_library_video(file_name="video.mp4"))

    assert str(response.path) == str(file_path)
    assert response.media_type == "video/mp4"
    assert "inline" in response.headers["content-disposition"]


def test_handle_transfer_library_video_returns_attachment(monkeypatch, tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(b"video-data")
    monkeypatch.setattr("src.controllers.library.transfer_video_file", lambda _: file_path)

    response = cast(FileResponse, handle_transfer_library_video(file_name="video.mp4"))

    assert str(response.path) == str(file_path)
    assert response.media_type == "video/mp4"
    assert "attachment" in response.headers["content-disposition"]


def test_handle_transfer_library_videos_returns_zip_attachment(monkeypatch, tmp_path):
    first_file = tmp_path / "video-1.mp4"
    second_file = tmp_path / "video-2.webm"
    archive_path = tmp_path / "bundle.zip"
    first_file.write_text("first", encoding="utf-8")
    second_file.write_text("second", encoding="utf-8")
    archive_path.write_bytes(b"zip-data")

    monkeypatch.setattr("src.controllers.library.transfer_video_files", lambda _: [first_file, second_file])
    monkeypatch.setattr("src.controllers.library.build_transfer_archive", lambda _: archive_path)

    response = cast(FileResponse, handle_transfer_library_videos(file_names=["video-1.mp4", "video-2.webm"]))

    assert str(response.path) == str(archive_path)
    assert response.media_type == "application/zip"
    assert "attachment" in response.headers["content-disposition"]


def test_handle_transfer_library_videos_returns_single_attachment(monkeypatch, tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(b"video-data")
    monkeypatch.setattr("src.controllers.library.transfer_video_files", lambda _: [file_path])

    response = cast(FileResponse, handle_transfer_library_videos(file_names=["video.mp4"]))

    assert str(response.path) == str(file_path)
    assert response.media_type == "video/mp4"
    assert "attachment" in response.headers["content-disposition"]


def test_delete_resolved_file_wraps_os_error(monkeypatch, tmp_path):
    file_path = tmp_path / "video.mp4"
    file_path.write_text("data", encoding="utf-8")

    def fail_unlink(*args, **kwargs):
        raise OSError("locked")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    try:
        _delete_resolved_file(file_path)
    except LibraryServiceError as exc:
        assert "não foi possível remover" in str(exc).lower()
    else:
        raise AssertionError("LibraryServiceError was expected")


def test_rename_resolved_file_wraps_os_error(monkeypatch, tmp_path):
    source_path = tmp_path / "video.mp4"
    destination_path = tmp_path / "novo-video.mp4"
    source_path.write_text("data", encoding="utf-8")

    def fail_rename(*args, **kwargs):
        raise OSError("busy")

    monkeypatch.setattr(Path, "rename", fail_rename)

    try:
        _rename_resolved_file(source_path, destination_path)
    except LibraryServiceError as exc:
        assert "não foi possível renomear" in str(exc).lower()
    else:
        raise AssertionError("LibraryServiceError was expected")


def test_build_renamed_file_path_rejects_empty_name(tmp_path):
    source_file = tmp_path / "video.mp4"
    source_file.write_text("data", encoding="utf-8")

    try:
        _build_renamed_file_path(source_file, "   ")
    except LibraryServiceError as exc:
        assert "nome válido" in str(exc).lower()
    else:
        raise AssertionError("LibraryServiceError was expected")


def test_build_renamed_file_path_rejects_extension_change(tmp_path):
    source_file = tmp_path / "video.mp4"
    source_file.write_text("data", encoding="utf-8")

    try:
        _build_renamed_file_path(source_file, "video.webm")
    except LibraryServiceError as exc:
        assert "extensão" in str(exc).lower()
    else:
        raise AssertionError("LibraryServiceError was expected")


def test_build_renamed_file_path_appends_current_extension_when_missing(tmp_path):
    source_file = tmp_path / "video.mp4"
    source_file.write_text("data", encoding="utf-8")

    destination_path = _build_renamed_file_path(source_file, "novo-video")

    assert destination_path == tmp_path / "novo-video.mp4"


def test_build_renamed_file_path_rejects_name_collision(tmp_path):
    source_file = tmp_path / "video.mp4"
    source_file.write_text("data", encoding="utf-8")
    (tmp_path / "novo-video.mp4").write_text("existing", encoding="utf-8")

    try:
        _build_renamed_file_path(source_file, "novo-video.mp4")
    except LibraryServiceError as exc:
        assert "já existe um arquivo" in str(exc).lower()
    else:
        raise AssertionError("LibraryServiceError was expected")
