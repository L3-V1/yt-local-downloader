from __future__ import annotations

import json
import logging
import mimetypes
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, TypedDict

from mutagen import File as MutagenFile

from src.services.download import DOWNLOADS_DIR
from src.services.yt_dlp import build_subprocess_env, find_executable

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".mov"}
LOGGER = logging.getLogger(__name__)


class LibraryServiceError(Exception):
    """Raised when a library operation cannot be completed safely."""


@dataclass(slots=True)
class VideoLibraryItem:
    file_name: str
    title: str
    extension: str
    size_bytes: int
    size_display: str
    modified_at: str
    duration_display: str
    resolution: str
    video_codec: str
    audio_codec: str


class Mp4Box(TypedDict):
    type: str
    start: int
    end: int
    data_offset: int
    data_end: int


def list_downloaded_videos() -> list[VideoLibraryItem]:
    """List downloaded media files from the local downloads directory.

    Returns:
        A reverse-chronological list of supported media files already saved locally.
    """
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    items: list[VideoLibraryItem] = []

    for file_path in sorted(DOWNLOADS_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not file_path.is_file() or file_path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
            continue
        items.append(_build_library_item(file_path))

    return items


def open_video_file(file_name: str) -> Path:
    """Resolve a downloaded media file for browser playback or download.

    Args:
        file_name: Name of the file stored inside the local downloads directory.

    Returns:
        The validated file path that can be streamed by the HTTP layer.
    """
    return _resolve_download_file(file_name)


def delete_video_file(file_name: str) -> None:
    """Delete a downloaded media file from the downloads directory.

    Args:
        file_name: Name of the file stored inside the local downloads directory.
    """
    file_path = _resolve_download_file(file_name)
    _delete_resolved_file(file_path)


def delete_video_files(file_names: list[str]) -> int:
    """Delete multiple downloaded media files from the downloads directory.

    Args:
        file_names: Selected file names from the local downloads directory.

    Returns:
        The number of deleted files.
    """
    resolved_files = _resolve_download_files(file_names)
    for file_path in resolved_files:
        _delete_resolved_file(file_path)
    return len(resolved_files)


def rename_video_file(file_name: str, new_file_name: str) -> Path:
    """Rename a downloaded media file inside the local downloads directory.

    Args:
        file_name: Current file name stored inside the local downloads directory.
        new_file_name: New file name requested by the user.

    Returns:
        The final path of the renamed file.
    """
    file_path = _resolve_download_file(file_name)
    renamed_file_path = _build_renamed_file_path(file_path, new_file_name)
    _rename_resolved_file(file_path, renamed_file_path)
    return renamed_file_path


def transfer_video_file(file_name: str) -> Path:
    """Resolve a downloaded media file for HTTP download transfer.

    Args:
        file_name: Name of the file stored inside the local downloads directory.

    Returns:
        The validated file path that can be returned as an attachment.
    """
    return _resolve_download_file(file_name)


def transfer_video_files(file_names: list[str]) -> list[Path]:
    """Resolve multiple downloaded media files for HTTP download transfer.

    Args:
        file_names: Selected file names from the local downloads directory.

    Returns:
        The validated file paths that can be bundled for download.
    """
    return _resolve_download_files(file_names)


def _resolve_download_file(file_name: str) -> Path:
    normalized_name = Path(file_name).name
    if not normalized_name or normalized_name != file_name:
        raise LibraryServiceError("Nome de arquivo inválido.")

    resolved_path = (DOWNLOADS_DIR / normalized_name).resolve()
    downloads_root = DOWNLOADS_DIR.resolve()

    if not resolved_path.is_relative_to(downloads_root):
        raise LibraryServiceError("O arquivo solicitado está fora da biblioteca local.")
    if not resolved_path.exists() or not resolved_path.is_file():
        raise LibraryServiceError("O arquivo solicitado não foi encontrado.")

    return resolved_path


def _resolve_download_files(file_names: list[str]) -> list[Path]:
    normalized_file_names = _normalize_file_names(file_names)
    return [_resolve_download_file(file_name) for file_name in normalized_file_names]


def _normalize_file_names(file_names: list[str]) -> list[str]:
    normalized_names: list[str] = []
    seen_names: set[str] = set()

    for raw_name in file_names:
        normalized_name = raw_name.strip()
        if not normalized_name or normalized_name in seen_names:
            continue
        normalized_names.append(normalized_name)
        seen_names.add(normalized_name)

    if not normalized_names:
        raise LibraryServiceError("Selecione pelo menos um vídeo para executar esta ação.")

    return normalized_names


def get_video_media_type(file_path: Path) -> str:
    media_type, _ = mimetypes.guess_type(file_path.name)
    return media_type or "application/octet-stream"


def build_transfer_archive(file_paths: list[Path]) -> Path:
    """Create a temporary zip archive for batch transfer downloads."""
    try:
        with tempfile.NamedTemporaryFile(prefix="yt-library-transfer-", suffix=".zip", delete=False) as temp_file:
            archive_path = Path(temp_file.name)

        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive_file:
            for file_path in file_paths:
                archive_file.write(file_path, arcname=file_path.name)
    except OSError as exc:
        LOGGER.warning("Failed to build transfer archive for %s files: %s", len(file_paths), exc)
        raise LibraryServiceError("Não foi possível preparar os vídeos selecionados para transferência.") from exc

    return archive_path


def _build_renamed_file_path(source_file_path: Path, raw_new_file_name: str) -> Path:
    normalized_name = _normalize_new_file_name(source_file_path, raw_new_file_name)
    destination_path = source_file_path.with_name(normalized_name)

    if destination_path == source_file_path:
        raise LibraryServiceError("Informe um nome diferente para renomear o vídeo.")
    if destination_path.exists():
        raise LibraryServiceError("Já existe um arquivo com esse nome na biblioteca.")

    return destination_path


def _normalize_new_file_name(source_file_path: Path, raw_new_file_name: str) -> str:
    normalized_name = Path(raw_new_file_name.strip()).name
    if not normalized_name:
        raise LibraryServiceError("Informe um nome válido para o vídeo.")
    if normalized_name != raw_new_file_name.strip():
        raise LibraryServiceError("O novo nome do arquivo é inválido.")

    destination_suffix = Path(normalized_name).suffix
    if not destination_suffix:
        normalized_name = f"{normalized_name}{source_file_path.suffix}"
        destination_suffix = source_file_path.suffix

    if destination_suffix.lower() != source_file_path.suffix.lower():
        raise LibraryServiceError("A extensão do arquivo não pode ser alterada nesta ação.")

    if normalized_name in {".", ".."}:
        raise LibraryServiceError("Informe um nome válido para o vídeo.")

    return normalized_name


def _delete_resolved_file(file_path: Path) -> None:
    try:
        file_path.unlink()
    except OSError as exc:
        LOGGER.warning("Failed to delete library video file=%s: %s", file_path.name, exc)
        raise LibraryServiceError("Não foi possível remover o vídeo selecionado.") from exc


def _rename_resolved_file(source_file_path: Path, destination_path: Path) -> None:
    try:
        source_file_path.rename(destination_path)
    except OSError as exc:
        LOGGER.warning(
            "Failed to rename library video source=%s destination=%s: %s",
            source_file_path.name,
            destination_path.name,
            exc,
        )
        raise LibraryServiceError("Não foi possível renomear o vídeo selecionado.") from exc


def _build_library_item(file_path: Path) -> VideoLibraryItem:
    metadata = _probe_media_metadata(file_path)
    file_stat = file_path.stat()

    return VideoLibraryItem(
        file_name=file_path.name,
        title=_build_display_title(file_path.stem),
        extension=file_path.suffix.lower().lstrip(".") or "desconhecido",
        size_bytes=file_stat.st_size,
        size_display=_format_file_size(file_stat.st_size),
        modified_at=datetime.fromtimestamp(file_stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
        duration_display=metadata["duration_display"],
        resolution=metadata["resolution"],
        video_codec=metadata["video_codec"],
        audio_codec=metadata["audio_codec"],
    )


def _probe_media_metadata(file_path: Path) -> dict[str, str]:
    ffprobe_executable = find_executable("ffprobe")
    if ffprobe_executable is None:
        return _probe_media_metadata_without_ffprobe(file_path)

    command = [
        ffprobe_executable,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height",
        "-of",
        "json",
        str(file_path),
    ]

    try:
        completed_process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=build_subprocess_env(),
        )
    except OSError as exc:
        LOGGER.warning("ffprobe execution failed for file=%s: %s", file_path.name, exc)
        return _probe_media_metadata_without_ffprobe(file_path)

    if completed_process.returncode != 0 or not completed_process.stdout.strip():
        LOGGER.debug(
            "ffprobe returned no usable metadata for file=%s returncode=%s",
            file_path.name,
            completed_process.returncode,
        )
        return _probe_media_metadata_without_ffprobe(file_path)

    try:
        payload = json.loads(completed_process.stdout)
    except json.JSONDecodeError as exc:
        LOGGER.warning("ffprobe returned invalid JSON for file=%s: %s", file_path.name, exc)
        return _probe_media_metadata_without_ffprobe(file_path)

    streams = payload.get("streams", [])
    format_data = payload.get("format", {})

    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})

    width = video_stream.get("width")
    height = video_stream.get("height")
    resolution = f"{width}x{height}" if width and height else "Não informado"

    return {
        "duration_display": _format_duration(format_data.get("duration")),
        "resolution": resolution,
        "video_codec": str(video_stream.get("codec_name") or "Não informado"),
        "audio_codec": str(audio_stream.get("codec_name") or "Não informado"),
    }


def _probe_media_metadata_without_ffprobe(file_path: Path) -> dict[str, str]:
    duration_seconds = _probe_duration_with_mutagen(file_path)
    if duration_seconds is None:
        duration_seconds = _probe_mp4_duration(file_path)
    width, height = _probe_mp4_resolution(file_path)

    return {
        "duration_display": _format_duration(duration_seconds),
        "resolution": f"{width}x{height}" if width and height else "Não informado",
        "video_codec": "Não informado",
        "audio_codec": "Não informado",
    }


def _probe_duration_with_mutagen(file_path: Path) -> float | None:
    try:
        media_file = MutagenFile(file_path)
    except OSError as exc:
        LOGGER.warning("Mutagen failed to read metadata for file=%s: %s", file_path.name, exc)
        return None

    if media_file is None or getattr(media_file, "info", None) is None:
        return None

    raw_length = getattr(media_file.info, "length", None)
    try:
        return float(raw_length) if raw_length is not None else None
    except (TypeError, ValueError):
        return None


def _probe_mp4_resolution(file_path: Path) -> tuple[int | None, int | None]:
    if file_path.suffix.lower() not in {".mp4", ".m4a", ".mov"}:
        return (None, None)

    try:
        with file_path.open("rb") as media_file:
            return _extract_mp4_resolution(media_file)
    except OSError as exc:
        LOGGER.warning("Failed to inspect MP4 boxes for file=%s: %s", file_path.name, exc)
        return (None, None)


def _probe_mp4_duration(file_path: Path) -> float | None:
    if file_path.suffix.lower() not in {".mp4", ".m4a", ".mov"}:
        return None

    try:
        with file_path.open("rb") as media_file:
            return _extract_mp4_duration(media_file)
    except OSError as exc:
        LOGGER.warning("Failed to inspect MP4 duration boxes for file=%s: %s", file_path.name, exc)
        return None


def _extract_mp4_duration(media_file: BinaryIO) -> float | None:
    moov_children = _find_mp4_box_children(media_file, ("moov",))
    mvhd_box = next((box for box in moov_children if box["type"] == "mvhd"), None)
    if mvhd_box is None:
        return None

    media_file.seek(int(mvhd_box["data_offset"]))
    payload = media_file.read(int(mvhd_box["data_end"]) - int(mvhd_box["data_offset"]))
    if len(payload) < 20:
        return None

    version = payload[0]
    if version == 1:
        if len(payload) < 32:
            return None
        timescale = int.from_bytes(payload[20:24], "big")
        duration = int.from_bytes(payload[24:32], "big")
    else:
        timescale = int.from_bytes(payload[12:16], "big")
        duration = int.from_bytes(payload[16:20], "big")

    if timescale <= 0 or duration <= 0:
        return None

    return duration / timescale


def _extract_mp4_resolution(media_file: BinaryIO) -> tuple[int | None, int | None]:
    moov_children = _find_mp4_box_children(media_file, ("moov",))
    if not moov_children:
        return (None, None)

    for trak_box in moov_children:
        if trak_box["type"] != "trak":
            continue
        track_children = _read_mp4_box_children(media_file, trak_box["data_offset"], trak_box["data_end"])
        if _read_mp4_handler_type(media_file, track_children) != "vide":
            continue

        width, height = _read_mp4_tkhd_resolution(media_file, track_children)
        if width and height:
            return (width, height)

    return (None, None)


def _find_mp4_box_children(media_file: BinaryIO, path: tuple[str, ...]) -> list[Mp4Box]:
    file_end = media_file.seek(0, 2)
    children = _read_mp4_box_children(media_file, 0, file_end)
    media_file.seek(0)

    for box_type in path:
        matching_box = next((box for box in children if box["type"] == box_type), None)
        if matching_box is None:
            return []
        children = _read_mp4_box_children(media_file, matching_box["data_offset"], matching_box["data_end"])

    return children


def _read_mp4_box_children(media_file: BinaryIO, start: int, end: int) -> list[Mp4Box]:
    children: list[Mp4Box] = []
    cursor = start

    while cursor + 8 <= end:
        media_file.seek(cursor)
        header = media_file.read(8)
        if len(header) < 8:
            break

        size = int.from_bytes(header[:4], "big")
        box_type = header[4:8].decode("latin-1")
        header_size = 8

        if size == 1:
            extended_size = media_file.read(8)
            if len(extended_size) < 8:
                break
            size = int.from_bytes(extended_size, "big")
            header_size = 16
        elif size == 0:
            size = end - cursor

        if size < header_size:
            break

        box_end = min(cursor + size, end)
        children.append(
            {
                "type": box_type,
                "start": cursor,
                "end": box_end,
                "data_offset": cursor + header_size,
                "data_end": box_end,
            }
        )
        cursor = box_end

    return children


def _read_mp4_handler_type(media_file: BinaryIO, track_children: list[Mp4Box]) -> str | None:
    mdia_box = next((box for box in track_children if box["type"] == "mdia"), None)
    if mdia_box is None:
        return None

    mdia_children = _read_mp4_box_children(media_file, mdia_box["data_offset"], mdia_box["data_end"])
    hdlr_box = next((box for box in mdia_children if box["type"] == "hdlr"), None)
    if hdlr_box is None:
        return None

    media_file.seek(int(hdlr_box["data_offset"]) + 8)
    return media_file.read(4).decode("latin-1") or None


def _read_mp4_tkhd_resolution(media_file: BinaryIO, track_children: list[Mp4Box]) -> tuple[int | None, int | None]:
    tkhd_box = next((box for box in track_children if box["type"] == "tkhd"), None)
    if tkhd_box is None:
        return (None, None)

    media_file.seek(int(tkhd_box["data_offset"]))
    tkhd_payload = media_file.read(int(tkhd_box["data_end"]) - int(tkhd_box["data_offset"]))
    if len(tkhd_payload) < 8:
        return (None, None)

    width_raw = int.from_bytes(tkhd_payload[-8:-4], "big")
    height_raw = int.from_bytes(tkhd_payload[-4:], "big")
    return (width_raw >> 16 or None, height_raw >> 16 or None)


def _build_display_title(file_stem: str) -> str:
    cleaned_title = file_stem.rsplit(" [", maxsplit=1)[0]
    return cleaned_title.replace("_", " ").strip() or file_stem


def _format_file_size(size_bytes: int) -> str:
    size_units = ["B", "KB", "MB", "GB", "TB"]
    size_value = float(size_bytes)

    for unit in size_units:
        if size_value < 1024 or unit == size_units[-1]:
            return f"{size_value:.1f} {unit}"
        size_value /= 1024

    return f"{size_bytes} B"


def _format_duration(raw_duration: object) -> str:
    if isinstance(raw_duration, bool):
        return "Não informado"
    if not isinstance(raw_duration, (int, float, str)):
        return "Não informado"
    try:
        duration_seconds = int(float(raw_duration))
    except (TypeError, ValueError):
        return "Não informado"

    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
