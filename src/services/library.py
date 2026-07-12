from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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


def open_video_file(file_name: str) -> None:
    """Open a downloaded media file with the default local player.

    Args:
        file_name: Name of the file stored inside the local downloads directory.
    """
    file_path = _resolve_download_file(file_name)
    try:
        os.startfile(file_path)  # type: ignore[attr-defined]
    except OSError as exc:
        LOGGER.warning("Failed to open library video file=%s: %s", file_path.name, exc)
        raise LibraryServiceError("Não foi possível abrir o vídeo selecionado.") from exc


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
    """Move a downloaded media file to a user-selected directory.

    Args:
        file_name: Name of the file stored inside the local downloads directory.

    Returns:
        The final destination path used for the moved file.
    """
    file_path = _resolve_download_file(file_name)
    target_directory = _select_transfer_directory()
    destination_path = _build_transfer_destination_path(file_path, target_directory)
    _move_resolved_file(file_path, destination_path)
    return destination_path


def transfer_video_files(file_names: list[str]) -> list[Path]:
    """Move multiple downloaded media files to a user-selected directory.

    Args:
        file_names: Selected file names from the local downloads directory.

    Returns:
        The final destination paths used for the moved files.
    """
    resolved_files = _resolve_download_files(file_names)
    target_directory = _select_transfer_directory()
    destination_paths = _build_transfer_destination_paths(resolved_files, target_directory)

    moved_paths: list[Path] = []
    for source_file_path, destination_path in zip(resolved_files, destination_paths):
        _move_resolved_file(source_file_path, destination_path)
        moved_paths.append(destination_path)

    return moved_paths


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


def _select_transfer_directory() -> Path:
    try:
        import tkinter as tk
        from tkinter import TclError, filedialog
    except ImportError as exc:  # pragma: no cover - depends on local GUI support
        raise LibraryServiceError("O seletor de diretório não está disponível neste ambiente.") from exc

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            selected_directory = filedialog.askdirectory(
                title="Selecione o diretório de destino para transferir os vídeos"
            )
        finally:
            root.destroy()
    except TclError as exc:  # pragma: no cover - depends on local GUI support
        raise LibraryServiceError("O seletor de diretório não pôde ser aberto neste ambiente.") from exc

    if not selected_directory:
        raise LibraryServiceError("Nenhum diretório foi selecionado para a transferência.")

    target_directory = Path(selected_directory).expanduser().resolve()
    if not target_directory.exists() or not target_directory.is_dir():
        raise LibraryServiceError("O diretório selecionado não é válido para a transferência.")

    return target_directory


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


def _move_resolved_file(source_file_path: Path, destination_path: Path) -> None:
    try:
        shutil.move(str(source_file_path), str(destination_path))
    except OSError as exc:
        LOGGER.warning(
            "Failed to transfer library video source=%s destination=%s: %s",
            source_file_path.name,
            destination_path,
            exc,
        )
        raise LibraryServiceError("Não foi possível transferir o vídeo selecionado.") from exc


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


def _build_transfer_destination_path(source_file_path: Path, target_directory: Path) -> Path:
    destination_path = target_directory / source_file_path.name
    if destination_path.resolve() == source_file_path.resolve():
        raise LibraryServiceError("O arquivo já está no diretório selecionado.")

    if not destination_path.exists():
        return destination_path

    stem = destination_path.stem
    suffix = destination_path.suffix

    for index in range(1, 1_000):
        candidate = target_directory / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate

    raise LibraryServiceError("Não foi possível definir um nome de destino livre para a transferência.")


def _build_transfer_destination_paths(source_file_paths: list[Path], target_directory: Path) -> list[Path]:
    reserved_names = {item.name for item in target_directory.iterdir()}
    destination_paths: list[Path] = []

    for source_file_path in source_file_paths:
        destination_path = _build_reserved_transfer_destination_path(
            source_file_path,
            target_directory,
            reserved_names,
        )
        reserved_names.add(destination_path.name)
        destination_paths.append(destination_path)

    return destination_paths


def _build_reserved_transfer_destination_path(
    source_file_path: Path,
    target_directory: Path,
    reserved_names: set[str],
) -> Path:
    base_destination_path = target_directory / source_file_path.name
    if base_destination_path.resolve() == source_file_path.resolve():
        raise LibraryServiceError("Um dos arquivos selecionados já está no diretório de destino.")

    if source_file_path.name not in reserved_names:
        return base_destination_path

    stem = base_destination_path.stem
    suffix = base_destination_path.suffix

    for index in range(1, 1_000):
        candidate_name = f"{stem} ({index}){suffix}"
        if candidate_name not in reserved_names:
            return target_directory / candidate_name

    raise LibraryServiceError("Não foi possível definir nomes de destino livres para a transferência.")


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
        return _empty_media_metadata()

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
        return _empty_media_metadata()

    if completed_process.returncode != 0 or not completed_process.stdout.strip():
        LOGGER.debug(
            "ffprobe returned no usable metadata for file=%s returncode=%s",
            file_path.name,
            completed_process.returncode,
        )
        return _empty_media_metadata()

    try:
        payload = json.loads(completed_process.stdout)
    except json.JSONDecodeError as exc:
        LOGGER.warning("ffprobe returned invalid JSON for file=%s: %s", file_path.name, exc)
        return _empty_media_metadata()

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


def _empty_media_metadata() -> dict[str, str]:
    return {
        "duration_display": "Não informado",
        "resolution": "Não informado",
        "video_codec": "Não informado",
        "audio_codec": "Não informado",
    }


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
    try:
        duration_seconds = int(float(raw_duration))
    except (TypeError, ValueError):
        return "Não informado"

    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
