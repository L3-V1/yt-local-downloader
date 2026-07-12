from __future__ import annotations

import logging
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, TextIO
from urllib.parse import urlparse

from fastapi import BackgroundTasks

from src.services.log import add_application_log
from src.services.yt_dlp import (
    build_subprocess_env,
    get_ffmpeg_location,
    get_preferred_js_runtime,
    get_remote_component_args,
)

DOWNLOADS_DIR = Path(__file__).resolve().parents[2] / "downloads"
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
StatusType = Literal["Em andamento", "Concluido", "Erro"]
ErrorType = Literal["timeout_total", "timeout_conexao", "sabr", "http_403", "startup", "desconhecido"]
VideoFormat = Literal["mp4", "webm", "original"]
VideoQuality = Literal["best", "1080", "720", "480"]
SOCKET_TIMEOUT_SECONDS = 10
RETRY_COUNT = 6
FRAGMENT_RETRY_COUNT = 6
EXTRACTOR_RETRY_COUNT = 3
FILE_ACCESS_RETRY_COUNT = 3
HTTP_RETRY_SLEEP = "exp=1:8"
FRAGMENT_RETRY_SLEEP = "fragment:exp=1:12"
EXTRACTOR_RETRY_SLEEP = "extractor:linear=1:3"
PROGRESS_PATTERN = re.compile(
    r"\[download\]\s+(?P<percent>\d+(?:\.\d+)?)%\s+of\s+(?P<total>.+?)\s+at\s+(?P<speed>.+?)\s+ETA\s+(?P<eta>\S+)",
    re.IGNORECASE,
)
LOGGER = logging.getLogger(__name__)


class DownloadRequestError(Exception):
    """Raised when a download request is invalid."""


@dataclass(slots=True)
class DownloadFailure:
    error_type: ErrorType
    message: str


@dataclass(slots=True)
class DownloadProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out_before_progress: bool = False


@dataclass(slots=True)
class DownloadItem:
    id: str
    video_url: str
    status: StatusType
    created_at: datetime
    video_format: VideoFormat
    video_quality: VideoQuality
    file_name: str | None = None
    error_message: str | None = None
    error_type: ErrorType | None = None
    progress_percent: float = 0.0
    progress_text: str = "Aguardando início"
    speed_text: str | None = None
    eta_text: str | None = None
    finished_at: datetime | None = None

    @property
    def created_at_display(self) -> str:
        return self.created_at.strftime("%d/%m/%Y %H:%M:%S")

    @property
    def created_at_iso(self) -> str:
        return self.created_at.isoformat()

    @property
    def finished_at_iso(self) -> str | None:
        return self.finished_at.isoformat() if self.finished_at else None

    def to_dict(self) -> dict[str, str | float | None]:
        return {
            "id": self.id,
            "video_url": self.video_url,
            "status": self.status,
            "created_at_display": self.created_at_display,
            "created_at_iso": self.created_at_iso,
            "finished_at_iso": self.finished_at_iso,
            "file_name": self.file_name,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "progress_percent": round(self.progress_percent, 1),
            "progress_text": self.progress_text,
            "speed_text": self.speed_text,
            "eta_text": self.eta_text,
            "video_format": self.video_format,
            "video_quality": self.video_quality,
        }


@dataclass(slots=True)
class DownloadAttempt:
    label: str
    extra_args: list[str] = field(default_factory=list)
    force_ipv4: bool = False
    http_chunk_size: str | None = None
    retry_count: int = RETRY_COUNT
    fragment_retry_count: int = FRAGMENT_RETRY_COUNT


@dataclass(slots=True)
class DownloadPreferences:
    video_format: VideoFormat
    video_quality: VideoQuality


@dataclass(slots=True)
class DownloadProgressSnapshot:
    percent: float
    progress_text: str
    speed_text: str | None = None
    eta_text: str | None = None


@dataclass
class DownloadRegistry:
    _items: dict[str, DownloadItem] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, item: DownloadItem) -> None:
        with self._lock:
            self._items[item.id] = item

    def update_status(
        self,
        download_id: str,
        *,
        status: StatusType,
        file_name: str | None = None,
        error_message: str | None = None,
        error_type: ErrorType | None = None,
        progress_percent: float | None = None,
        progress_text: str | None = None,
        speed_text: str | None = None,
        eta_text: str | None = None,
        finished: bool = False,
    ) -> None:
        with self._lock:
            item = self._items.get(download_id)
            if item is None:
                return
            item.status = status
            item.file_name = file_name
            item.error_message = error_message
            item.error_type = error_type
            if progress_percent is not None:
                item.progress_percent = max(0.0, min(100.0, progress_percent))
            if progress_text is not None:
                item.progress_text = progress_text
            item.speed_text = speed_text
            item.eta_text = eta_text
            item.finished_at = datetime.now() if finished else None

    def update_progress(self, download_id: str, progress: DownloadProgressSnapshot) -> None:
        with self._lock:
            item = self._items.get(download_id)
            if item is None:
                return
            item.progress_percent = max(0.0, min(100.0, progress.percent))
            item.progress_text = progress.progress_text
            item.speed_text = progress.speed_text
            item.eta_text = progress.eta_text

    def get(self, download_id: str) -> DownloadItem | None:
        with self._lock:
            return self._items.get(download_id)

    def list_downloads(self) -> list[DownloadItem]:
        with self._lock:
            return sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)

    def remove(self, download_id: str) -> bool:
        with self._lock:
            removed_item = self._items.pop(download_id, None)
            return removed_item is not None

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


download_registry = DownloadRegistry()
ALLOWED_VIDEO_FORMATS: tuple[VideoFormat, ...] = ("mp4", "webm", "original")
ALLOWED_VIDEO_QUALITIES: tuple[VideoQuality, ...] = ("best", "1080", "720", "480")


def enqueue_download(
    background_tasks: BackgroundTasks,
    video_url: str,
    *,
    video_format: str = "mp4",
    video_quality: str = "best",
) -> str:
    """Validate the URL, register the task, and schedule the download.

    Args:
        background_tasks: FastAPI background task registry for the request.
        video_url: Public YouTube URL selected by the user.

    Returns:
        The generated download identifier stored in memory.
    """
    normalized_url = _validate_youtube_url(video_url)
    preferences = _validate_download_preferences(video_format, video_quality)
    download_id = str(uuid.uuid4())
    item = DownloadItem(
        id=download_id,
        video_url=normalized_url,
        status="Em andamento",
        created_at=datetime.now(),
        video_format=preferences.video_format,
        video_quality=preferences.video_quality,
    )

    download_registry.add(item)
    background_tasks.add_task(_run_download_job, download_id, normalized_url, preferences)
    return download_id


def enqueue_retry_download(background_tasks: BackgroundTasks, *, download_id: str) -> str:
    """Requeue a failed download using the original URL and preferences.

    Args:
        background_tasks: FastAPI background task registry for the request.
        download_id: Identifier of the previous failed download.

    Returns:
        The generated identifier of the new queued download.
    """
    existing_item = download_registry.get(download_id)
    if existing_item is None:
        raise DownloadRequestError("O item selecionado não foi encontrado no histórico.")
    if existing_item.status != "Erro":
        raise DownloadRequestError("Somente downloads com erro podem ser reenviados.")

    return enqueue_download(
        background_tasks,
        existing_item.video_url,
        video_format=existing_item.video_format,
        video_quality=existing_item.video_quality,
    )


def _validate_youtube_url(video_url: str) -> str:
    normalized_url = video_url.strip()
    parsed = urlparse(normalized_url)

    if parsed.scheme not in {"http", "https"}:
        raise DownloadRequestError("Apenas URLs HTTP e HTTPS são permitidas.")
    if parsed.netloc.lower() not in ALLOWED_HOSTS:
        raise DownloadRequestError("Apenas URLs públicas do YouTube são permitidas.")
    if not parsed.path.strip("/"):
        raise DownloadRequestError("A URL do YouTube deve incluir o caminho do vídeo.")
    return normalized_url


def _validate_download_preferences(video_format: str, video_quality: str) -> DownloadPreferences:
    normalized_format = video_format.strip().lower()
    normalized_quality = video_quality.strip().lower()

    if normalized_format not in ALLOWED_VIDEO_FORMATS:
        raise DownloadRequestError("O formato de vídeo selecionado é inválido.")
    if normalized_quality not in ALLOWED_VIDEO_QUALITIES:
        raise DownloadRequestError("A qualidade de vídeo selecionada é inválida.")

    return DownloadPreferences(
        video_format=normalized_format,
        video_quality=normalized_quality,
    )


def _run_download_job(download_id: str, video_url: str, preferences: DownloadPreferences) -> None:
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    env = build_subprocess_env()
    attempted_labels: list[str] = []
    last_failure = DownloadFailure(
        error_type="desconhecido",
        message="O download falhou sem detalhes adicionais.",
    )
    download_registry.update_progress(
        download_id,
        DownloadProgressSnapshot(percent=0.0, progress_text="Preparando download"),
    )

    for attempt in _build_download_attempts():
        attempted_labels.append(attempt.label)
        command = _build_download_command(video_url, attempt, preferences)
        LOGGER.info(
            "Starting download attempt id=%s url=%s strategy=%s",
            download_id,
            video_url,
            attempt.label,
        )
        download_registry.update_progress(
            download_id,
            DownloadProgressSnapshot(
                percent=0.0,
                progress_text=f"Inicializando perfil {attempt.label}",
            ),
        )

        try:
            process_result = _execute_download_process(command, env, download_id=download_id)
        except OSError as exc:
            LOGGER.exception(
                "Failed to start download job id=%s url=%s strategy=%s",
                download_id,
                video_url,
                attempt.label,
            )
            download_registry.update_status(
                download_id,
                status="Erro",
                error_message=f"Falha ao iniciar o yt-dlp: {exc}",
                error_type="startup",
                progress_text="Falha ao iniciar",
                finished=True,
            )
            _log_download_failure(
                download_id=download_id,
                video_url=video_url,
                error_type="startup",
                message="Falha ao iniciar o yt-dlp.",
                details=str(exc),
            )
            return

        if process_result.timed_out_before_progress:
            last_failure = DownloadFailure(
                error_type="timeout_total",
                message=_build_initial_response_timeout_message(),
            )
            LOGGER.warning(
                "Download startup timed out for id=%s url=%s strategy=%s timeout=%ss",
                download_id,
                video_url,
                attempt.label,
                SOCKET_TIMEOUT_SECONDS,
            )
            if _is_last_attempt(attempt):
                download_registry.update_status(
                    download_id,
                    status="Erro",
                    error_message=last_failure.message,
                    error_type=last_failure.error_type,
                    progress_text="Sem resposta inicial",
                    finished=True,
                )
                _log_download_failure(
                    download_id=download_id,
                    video_url=video_url,
                    error_type=last_failure.error_type,
                    message=last_failure.message,
                    details=f"Tentativa: {attempt.label}",
                )
                return
            continue

        if process_result.returncode == 0:
            file_name = _extract_destination_file(process_result.stdout)
            LOGGER.info(
                "Download finished for id=%s url=%s strategy=%s file=%s",
                download_id,
                video_url,
                attempt.label,
                file_name,
            )
            download_registry.update_status(
                download_id,
                status="Concluido",
                file_name=file_name,
                progress_percent=100.0,
                progress_text="Concluído",
                finished=True,
            )
            return

        last_failure = _format_download_error(process_result.stderr or process_result.stdout)
        LOGGER.warning(
            "Download failed for id=%s url=%s strategy=%s returncode=%s type=%s details=%s",
            download_id,
            video_url,
            attempt.label,
            process_result.returncode,
            last_failure.error_type,
            last_failure.message,
        )

        if not _should_try_fallback(last_failure.message):
            break

    download_registry.update_status(
        download_id,
        status="Erro",
        error_message=last_failure.message,
        error_type=last_failure.error_type,
        progress_text="Falha na transferência",
        finished=True,
    )
    _log_download_failure(
        download_id=download_id,
        video_url=video_url,
        error_type=last_failure.error_type,
        message=last_failure.message,
        details=(
            "O download falhou mesmo apos aplicar os perfis de fallback disponiveis. "
            f"Perfis testados: {', '.join(attempted_labels)}."
        ),
    )


def _build_download_attempts() -> list[DownloadAttempt]:
    return [
        DownloadAttempt(label="default_resilient"),
        DownloadAttempt(
            label="android_ipv4_progressive",
            force_ipv4=True,
            http_chunk_size="1M",
            extra_args=[
                "--extractor-args",
                "youtube:player_client=android",
                "-f",
                "18/b[protocol=https][vcodec*=avc1][acodec*=mp4a]/18/b",
            ],
        ),
        DownloadAttempt(
            label="ios_ipv4_progressive",
            force_ipv4=True,
            http_chunk_size="1M",
            extra_args=[
                "--extractor-args",
                "youtube:player_client=ios",
                "-f",
                "18/b[protocol=https][vcodec*=avc1][acodec*=mp4a]/18/b",
            ],
        ),
        DownloadAttempt(
            label="ios_ipv4_hls",
            force_ipv4=True,
            http_chunk_size="1M",
            extra_args=[
                "--extractor-args",
                "youtube:player_client=ios",
                "-f",
                "b[protocol*=m3u8][ext=mp4]/b[protocol*=m3u8]/18/b",
            ],
        ),
        DownloadAttempt(
            label="conservative_small_chunks",
            force_ipv4=True,
            http_chunk_size="512K",
            retry_count=8,
            fragment_retry_count=8,
            extra_args=["-S", "res:480,+size,+br", "-f", "18/22/b[height<=480][ext=mp4]/b[height<=480]/b"],
        ),
        DownloadAttempt(
            label="audio_safe_fallback",
            force_ipv4=True,
            http_chunk_size="256K",
            retry_count=8,
            fragment_retry_count=8,
            extra_args=[
                "--extractor-args",
                "youtube:player_client=ios",
                "-f",
                "b[height<=360][protocol*=m3u8]/18/b[height<=360]/b",
            ],
        ),
    ]


def _is_last_attempt(attempt: DownloadAttempt) -> bool:
    attempts = _build_download_attempts()
    return attempt.label == attempts[-1].label


def _build_download_command(
    video_url: str,
    attempt: DownloadAttempt | None = None,
    preferences: DownloadPreferences | None = None,
) -> list[str]:
    selected_attempt = attempt or DownloadAttempt(label="default_resilient")
    selected_preferences = preferences or DownloadPreferences(video_format="mp4", video_quality="best")
    output_template = str(DOWNLOADS_DIR / "%(title).120s [%(id)s].%(ext)s")
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--socket-timeout",
        str(SOCKET_TIMEOUT_SECONDS),
        "--retries",
        str(selected_attempt.retry_count),
        "--fragment-retries",
        str(selected_attempt.fragment_retry_count),
        "--extractor-retries",
        str(EXTRACTOR_RETRY_COUNT),
        "--file-access-retries",
        str(FILE_ACCESS_RETRY_COUNT),
        "--retry-sleep",
        HTTP_RETRY_SLEEP,
        "--retry-sleep",
        FRAGMENT_RETRY_SLEEP,
        "--retry-sleep",
        EXTRACTOR_RETRY_SLEEP,
        "--no-playlist",
        "--restrict-filenames",
        "--output",
        output_template,
    ]

    command.extend(_build_preference_args(selected_preferences))

    if selected_attempt.force_ipv4:
        command.append("--force-ipv4")

    if selected_attempt.http_chunk_size is not None:
        command.extend(["--http-chunk-size", selected_attempt.http_chunk_size])

    ffmpeg_location = get_ffmpeg_location()
    if ffmpeg_location is not None:
        command.extend(["--ffmpeg-location", ffmpeg_location])

    runtime = get_preferred_js_runtime()
    if runtime is not None:
        command.extend(["--js-runtimes", runtime])
        command.extend(get_remote_component_args())

    if selected_attempt.extra_args:
        command.extend(selected_attempt.extra_args)

    command.append(video_url)

    return command


def _build_preference_args(preferences: DownloadPreferences) -> list[str]:
    sort_expression = _build_sort_expression(preferences)
    args = ["-S", sort_expression]

    target_extension = _resolve_target_extension(preferences.video_format)
    if target_extension is not None:
        args.extend(["--merge-output-format", target_extension, "--remux-video", target_extension])

    return args


def _build_sort_expression(preferences: DownloadPreferences) -> str:
    sort_fields: list[str] = []
    target_extension = _resolve_target_extension(preferences.video_format)

    if target_extension == "mp4":
        sort_fields.append("ext:mp4:m4a")
    elif target_extension == "webm":
        sort_fields.append("ext:webm")

    if preferences.video_quality != "best":
        sort_fields.append(f"res:{preferences.video_quality}")

    if not sort_fields:
        sort_fields.append("res")

    return ",".join(sort_fields)


def _resolve_target_extension(video_format: VideoFormat) -> str | None:
    if video_format == "original":
        return None
    return video_format


def _execute_download_process(
    command: list[str],
    env: dict[str, str],
    *,
    download_id: str,
) -> DownloadProcessResult:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    output_queue: queue.SimpleQueue[str] = queue.SimpleQueue()

    stdout_thread = threading.Thread(
        target=_read_process_stream,
        args=(process.stdout, stdout_lines, output_queue),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_read_process_stream,
        args=(process.stderr, stderr_lines, output_queue),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    progress_started = False
    deadline = time.monotonic() + SOCKET_TIMEOUT_SECONDS

    while process.poll() is None and not progress_started:
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            _terminate_process(process)
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            return DownloadProcessResult(
                returncode=1,
                stdout="".join(stdout_lines),
                stderr="".join(stderr_lines),
                timed_out_before_progress=True,
            )

        try:
            next_line = output_queue.get(timeout=min(0.2, remaining_seconds))
        except queue.Empty:
            continue

        progress_snapshot = _parse_progress_line(next_line)
        if progress_snapshot is not None:
            progress_started = True
            download_registry.update_progress(download_id, progress_snapshot)
            continue

        if _indicates_download_progress(next_line):
            progress_started = True
            download_registry.update_progress(
                download_id,
                DownloadProgressSnapshot(percent=0.0, progress_text="Conectado, iniciando transferência"),
            )

    while process.poll() is None:
        try:
            next_line = output_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        progress_snapshot = _parse_progress_line(next_line)
        if progress_snapshot is None:
            continue
        download_registry.update_progress(download_id, progress_snapshot)

    returncode = process.wait()
    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)
    return DownloadProcessResult(
        returncode=returncode,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
    )


def _read_process_stream(
    stream: TextIO | None,
    collected_lines: list[str],
    output_queue: queue.SimpleQueue[str],
) -> None:
    if stream is None:
        return

    try:
        for line in iter(stream.readline, ""):
            collected_lines.append(line)
            output_queue.put(line)
    finally:
        stream.close()


def _terminate_process(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _indicates_download_progress(output_line: str) -> bool:
    normalized_line = output_line.strip().lower()
    if not normalized_line:
        return False

    progress_markers = (
        "[download] destination:",
        "[download] ",
        "[merger] merging formats into",
        "has already been downloaded",
    )
    if normalized_line.startswith("[download]") and "%" in normalized_line:
        return True
    return any(marker in normalized_line for marker in progress_markers)


def _parse_progress_line(output_line: str) -> DownloadProgressSnapshot | None:
    normalized_line = output_line.strip()
    if not normalized_line:
        return None

    if "has already been downloaded" in normalized_line.lower():
        return DownloadProgressSnapshot(percent=100.0, progress_text="Arquivo já disponível")

    if "[download] destination:" in normalized_line.lower():
        return DownloadProgressSnapshot(percent=0.0, progress_text="Arquivo de destino preparado")

    progress_match = PROGRESS_PATTERN.search(normalized_line)
    if progress_match is None:
        return None

    percent = float(progress_match.group("percent"))
    speed_text = progress_match.group("speed").strip()
    eta_text = progress_match.group("eta").strip()
    total_text = progress_match.group("total").strip()

    return DownloadProgressSnapshot(
        percent=percent,
        progress_text=f"{percent:.1f}% de {total_text}",
        speed_text=speed_text,
        eta_text=eta_text,
    )


def _build_initial_response_timeout_message() -> str:
    return (
        "O YouTube não respondeu ao início do download em até 10 segundos. "
        "Tente novamente ou teste outro vídeo."
    )


def _should_try_fallback(error_message: str) -> bool:
    lowered_message = error_message.lower()
    fallback_markers = (
        "conexao com o youtube expirou",
        "timed out",
        "connection to",
        "connection aborted",
        "connection reset",
        "reset by peer",
        "failed to establish a new connection",
        "temporary failure in name resolution",
        "unable to download video data",
        "sabr-only streaming",
        "missing a url",
        "http error 403",
        "did not get any data blocks",
        "recusou o fluxo de midia",
        "recusou o fluxo de mídia",
    )
    return any(marker in lowered_message for marker in fallback_markers)


def _compact_process_message(message: str) -> str:
    return " ".join(line.strip() for line in message.splitlines() if line.strip())[:300]


def _format_download_error(message: str) -> DownloadFailure:
    compact_message = _compact_process_message(message)
    lowered_message = compact_message.lower()

    if "sabr-only streaming" in lowered_message or "missing a url" in lowered_message:
        return DownloadFailure(
            error_type="sabr",
            message=(
                "O YouTube forneceu este vídeo apenas com formatos SABR para a sessão atual, "
                "e o yt-dlp não conseguiu obter uma URL direta compatível. "
                "Tente novamente mais tarde ou teste outro vídeo."
            ),
        )

    if "http error 403" in lowered_message or "did not get any data blocks" in lowered_message:
        return DownloadFailure(
            error_type="http_403",
            message=(
                "O YouTube recusou o fluxo de mídia deste vídeo durante a transferência. "
                "Isso pode acontecer com alguns vídeos ou formatos específicos. Tente novamente mais tarde."
            ),
        )

    if (
        "timed out" in lowered_message
        or "winerror 10060" in lowered_message
        or "connection reset" in lowered_message
        or "reset by peer" in lowered_message
        or "connection aborted" in lowered_message
        or "failed to establish a new connection" in lowered_message
    ):
        return DownloadFailure(
            error_type="timeout_conexao",
            message=(
                "A conexão com o YouTube ficou 10 segundos sem resposta durante o download. "
                "Verifique sua rede, firewall, VPN ou proxy e tente novamente."
            ),
        )

    return DownloadFailure(
        error_type="desconhecido",
        message=compact_message or "O download falhou sem detalhes adicionais.",
    )


def _extract_destination_file(stdout: str) -> str | None:
    markers = ("[download] Destination:", "[Merger] Merging formats into")

    for line in stdout.splitlines():
        for marker in markers:
            if marker in line:
                return line.split(marker, maxsplit=1)[-1].strip().strip('"')
    return None


def _log_download_failure(
    *,
    download_id: str,
    video_url: str,
    error_type: ErrorType,
    message: str,
    details: str | None,
) -> None:
    details_parts = [f"Tipo: {error_type}", f"URL: {video_url}"]
    if details:
        details_parts.append(details)

    add_application_log(
        level="error",
        source="downloads",
        message=message,
        details=" | ".join(details_parts),
        reference_id=download_id,
    )
