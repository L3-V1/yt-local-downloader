from __future__ import annotations

from pathlib import Path

from src.services.library import (
    LibraryServiceError,
    _build_display_title,
    _build_renamed_file_path,
    _build_transfer_destination_path,
    _build_transfer_destination_paths,
    _delete_resolved_file,
    _format_duration,
    _format_file_size,
    _move_resolved_file,
    _normalize_file_names,
    _rename_resolved_file,
    _resolve_download_file,
)


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


def test_move_resolved_file_wraps_os_error(monkeypatch, tmp_path):
    source_path = tmp_path / "video.mp4"
    destination_path = tmp_path / "video (1).mp4"
    source_path.write_text("data", encoding="utf-8")

    def fail_move(*args, **kwargs):
        raise OSError("busy")

    monkeypatch.setattr("src.services.library.shutil.move", fail_move)

    try:
        _move_resolved_file(source_path, destination_path)
    except LibraryServiceError as exc:
        assert "não foi possível transferir" in str(exc).lower()
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


def test_build_transfer_destination_path_rejects_same_directory(tmp_path):
    source_file = tmp_path / "video.mp4"
    source_file.write_text("data", encoding="utf-8")

    try:
        _build_transfer_destination_path(source_file, tmp_path)
    except LibraryServiceError as exc:
        assert "já está no diretório selecionado" in str(exc)
    else:
        raise AssertionError("LibraryServiceError was expected")


def test_build_transfer_destination_path_generates_unique_name(tmp_path):
    source_directory = tmp_path / "source"
    source_directory.mkdir()
    source_file = source_directory / "video.mp4"
    source_file.write_text("data", encoding="utf-8")

    target_directory = tmp_path / "target"
    target_directory.mkdir()
    (target_directory / "video.mp4").write_text("existing", encoding="utf-8")

    destination = _build_transfer_destination_path(source_file, target_directory)

    assert destination == target_directory / "video (1).mp4"


def test_build_transfer_destination_paths_reserves_names_between_selected_files(tmp_path):
    source_directory = tmp_path / "source"
    source_directory.mkdir()
    first_source = source_directory / "video.mp4"
    second_source = source_directory / "video.webm"
    first_source.write_text("data", encoding="utf-8")
    second_source.write_text("data", encoding="utf-8")

    target_directory = tmp_path / "target"
    target_directory.mkdir()
    (target_directory / "video.mp4").write_text("existing", encoding="utf-8")

    destinations = _build_transfer_destination_paths([first_source, second_source], target_directory)

    assert destinations == [
        target_directory / "video (1).mp4",
        target_directory / "video.webm",
    ]
