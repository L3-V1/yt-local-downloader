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

export function syncActionsState(copyButton, openAppButton, hasVideoUrl) {
    if (copyButton) {
        copyButton.disabled = !hasVideoUrl;
    }

    if (openAppButton) {
        openAppButton.disabled = !hasVideoUrl;
    }
}
