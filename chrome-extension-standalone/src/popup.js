import { getPopupElements } from "./dom.js";
import { loadSavedSettings, saveApiUrl, saveDownloadPreferences } from "./storage.js";
import { isSupportedYoutubeUrl } from "./url.js";
import { setStatusMessage, syncActionsState, updateDetectedVideo } from "./ui.js";

const popupElements = getPopupElements();
let currentVideoUrl = "";
let isDownloading = false;

async function initializePopup() {
    const savedSettings = await loadSavedSettings();
    applySavedSettings(savedSettings);
    bindPopupEvents();
    await detectCurrentYoutubeVideo();
    applyLastStatus(savedSettings.lastStatus);
}

function applySavedSettings(savedSettings) {
    if (popupElements.apiBaseUrlInput) {
        popupElements.apiBaseUrlInput.value = savedSettings.apiBaseUrl;
    }
    if (popupElements.videoFormatSelect) {
        popupElements.videoFormatSelect.value = savedSettings.videoFormat;
    }
    if (popupElements.videoQualitySelect) {
        popupElements.videoQualitySelect.value = savedSettings.videoQuality;
    }
}

function applyLastStatus(lastStatus) {
    if (!lastStatus?.message) {
        return;
    }

    setStatusMessage(
        popupElements.statusMessage,
        lastStatus.message,
        lastStatus.tone || "neutral",
    );
}

function bindPopupEvents() {
    popupElements.downloadButton?.addEventListener("click", startExperimentalDownload);
    popupElements.apiBaseUrlInput?.addEventListener("change", persistSettings);
    popupElements.apiBaseUrlInput?.addEventListener("blur", persistSettings);
    popupElements.videoFormatSelect?.addEventListener("change", persistSettings);
    popupElements.videoQualitySelect?.addEventListener("change", persistSettings);
}

async function persistSettings() {
    if (!popupElements.apiBaseUrlInput || !popupElements.videoFormatSelect || !popupElements.videoQualitySelect) {
        return;
    }

    popupElements.apiBaseUrlInput.value = await saveApiUrl(popupElements.apiBaseUrlInput.value);
    await saveDownloadPreferences(
        popupElements.videoFormatSelect.value,
        popupElements.videoQualitySelect.value,
    );
}

async function detectCurrentYoutubeVideo() {
    const [activeTab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
    });

    const detectedUrl = activeTab?.url || "";
    if (!isSupportedYoutubeUrl(detectedUrl)) {
        setCurrentVideoUrl("");
        setStatusMessage(
            popupElements.statusMessage,
            "Abra um vídeo compatível do YouTube.",
            "danger",
        );
        return;
    }

    setCurrentVideoUrl(detectedUrl);
}

function setCurrentVideoUrl(videoUrl) {
    currentVideoUrl = videoUrl;
    updateDetectedVideo(popupElements.videoUrlText, videoUrl);
    syncActionsState(popupElements.downloadButton, Boolean(videoUrl), isDownloading);
}

async function startExperimentalDownload() {
    if (!currentVideoUrl || isDownloading || !popupElements.apiBaseUrlInput || !popupElements.videoFormatSelect || !popupElements.videoQualitySelect) {
        return;
    }

    try {
        isDownloading = true;
        syncActionsState(popupElements.downloadButton, true, true);
        setStatusMessage(popupElements.statusMessage, "Preparando download...", "neutral");

        const normalizedApiUrl = await saveApiUrl(popupElements.apiBaseUrlInput.value);
        popupElements.apiBaseUrlInput.value = normalizedApiUrl;
        await saveDownloadPreferences(
            popupElements.videoFormatSelect.value,
            popupElements.videoQualitySelect.value,
        );
        await startBackgroundDownload({
            apiBaseUrl: normalizedApiUrl,
            videoUrl: currentVideoUrl,
            videoFormat: popupElements.videoFormatSelect.value,
            videoQuality: popupElements.videoQualitySelect.value,
        });

        isDownloading = false;
        syncActionsState(popupElements.downloadButton, true, false);
        setStatusMessage(
            popupElements.statusMessage,
            "Seletor de destino aberto no Chrome.",
            "success",
        );
    } catch (error) {
        isDownloading = false;
        syncActionsState(popupElements.downloadButton, true, false);
        setStatusMessage(
            popupElements.statusMessage,
            error instanceof Error ? error.message : "Não foi possível iniciar o download agora.",
            "danger",
        );
    }
}

async function startBackgroundDownload(payload) {
    const response = await chrome.runtime.sendMessage({
        type: "start-download",
        payload,
    });

    if (!response?.ok) {
        throw new Error(response?.message || "Não foi possível iniciar o download.");
    }

    return response;
}

initializePopup().catch((error) => {
    console.error("Falha ao inicializar a extensão v2.", error);
    setStatusMessage(
        popupElements.statusMessage,
        "Não foi possível iniciar a extensão agora.",
        "danger",
    );
});
