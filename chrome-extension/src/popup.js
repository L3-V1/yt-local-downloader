import { getPopupElements } from "./dom.js";
import { buildAppSearchUrl, buildApplicationUrlPatterns, isSupportedYoutubeUrl } from "./url.js";
import { loadSavedAppUrl, saveAppUrl } from "./storage.js";
import { setStatusMessage, syncActionsState } from "./ui.js";

const popupElements = getPopupElements();
let currentVideoUrl = "";

function updateDetectedVideo(url) {
    currentVideoUrl = url;
    if (popupElements.videoUrlText) {
        popupElements.videoUrlText.textContent = url || "Abra um vídeo do YouTube para continuar.";
    }

    syncActionsState(
        popupElements.copyButton,
        popupElements.openAppButton,
        Boolean(url),
    );
}

async function detectCurrentYoutubeVideo() {
    const [activeTab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
    });

    const detectedUrl = activeTab?.url || "";
    if (!isSupportedYoutubeUrl(detectedUrl)) {
        updateDetectedVideo("");
        setStatusMessage(
            popupElements.statusMessage,
            "Nenhum link de vídeo compatível foi encontrado na aba atual.",
            "danger",
        );
        return;
    }

    updateDetectedVideo(detectedUrl);
    setStatusMessage(
        popupElements.statusMessage,
        "Vídeo detectado. Você já pode enviar o link para a aplicação.",
        "success",
    );
}

async function copyCurrentVideoUrl() {
    if (!currentVideoUrl) {
        return;
    }

    await navigator.clipboard.writeText(currentVideoUrl);
    setStatusMessage(
        popupElements.statusMessage,
        "Link copiado para a área de transferência.",
        "success",
    );
}

async function openAppWithCurrentVideo() {
    if (!currentVideoUrl || !popupElements.appBaseUrlInput) {
        return;
    }

    const normalizedAppUrl = await saveAppUrl(popupElements.appBaseUrlInput.value);
    popupElements.appBaseUrlInput.value = normalizedAppUrl;

    const targetUrl = buildAppSearchUrl(normalizedAppUrl, currentVideoUrl);
    const existingTabs = await chrome.tabs.query({
        url: buildApplicationUrlPatterns(normalizedAppUrl),
    });

    if (existingTabs.length > 0) {
        const targetTab = existingTabs[0];
        await chrome.tabs.update(targetTab.id, {
            active: true,
            url: targetUrl,
        });

        if (typeof targetTab.windowId === "number") {
            await chrome.windows.update(targetTab.windowId, { focused: true });
        }
    } else {
        await chrome.tabs.create({ url: targetUrl });
    }

    setStatusMessage(
        popupElements.statusMessage,
        "Aplicação aberta com o link preenchido no campo de busca.",
        "success",
    );
}

async function initializePopup() {
    if (popupElements.appBaseUrlInput) {
        popupElements.appBaseUrlInput.value = await loadSavedAppUrl();
        popupElements.appBaseUrlInput.addEventListener("change", async () => {
            popupElements.appBaseUrlInput.value = await saveAppUrl(popupElements.appBaseUrlInput.value);
        });
        popupElements.appBaseUrlInput.addEventListener("blur", async () => {
            popupElements.appBaseUrlInput.value = await saveAppUrl(popupElements.appBaseUrlInput.value);
        });
    }

    popupElements.copyButton?.addEventListener("click", copyCurrentVideoUrl);
    popupElements.openAppButton?.addEventListener("click", openAppWithCurrentVideo);
    await detectCurrentYoutubeVideo();
}

initializePopup().catch((error) => {
    console.error("Falha ao inicializar a extensão auxiliar.", error);
    setStatusMessage(
        popupElements.statusMessage,
        "Não foi possível iniciar a extensão agora.",
        "danger",
    );
});
