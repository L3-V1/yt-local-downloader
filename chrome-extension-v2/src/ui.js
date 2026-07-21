export function setStatusMessage(statusElement, message, tone = "neutral") {
    if (!statusElement) {
        return;
    }

    statusElement.textContent = message;
    statusElement.classList.remove("text-danger", "text-success", "text-body-muted");

    if (tone === "danger") {
        statusElement.classList.add("text-danger");
        return;
    }

    if (tone === "success") {
        statusElement.classList.add("text-success");
        return;
    }

    statusElement.classList.add("text-body-muted");
}

export function syncActionsState(downloadButton, hasVideoUrl, isDownloading) {
    if (downloadButton) {
        downloadButton.disabled = !hasVideoUrl || isDownloading;
        downloadButton.textContent = isDownloading ? "Baixando..." : "Baixar vídeo";
    }
}

export function updateDetectedVideo(videoUrlTextElement, videoUrl) {
    if (!videoUrlTextElement) {
        return;
    }

    videoUrlTextElement.textContent = videoUrl || "Abra um vídeo do YouTube para continuar.";
}
