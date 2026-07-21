import { requestDirectDownload } from "./api.js";
import { saveLastStatus } from "./storage.js";
import { normalizeDownloadFilename } from "./url.js";

function extractDownloadLink(responsePayload) {
    if (responsePayload.status === "redirect" || responsePayload.status === "tunnel") {
        const resolvedUrl = String(responsePayload.url || "").trim();
        if (!resolvedUrl) {
            throw new Error("A API experimental não retornou um link de download válido.");
        }
        return resolvedUrl;
    }

    if (responsePayload.status === "error") {
        throw new Error(responsePayload.text || "A API experimental retornou erro.");
    }

    if (responsePayload.status === "local-processing") {
        throw new Error("A API experimental exigiu processamento local adicional e este modo ainda não é suportado.");
    }

    if (responsePayload.status === "picker") {
        throw new Error("A API experimental retornou múltiplos itens e este caso ainda não é suportado.");
    }

    throw new Error("A API experimental retornou uma resposta inesperada.");
}

function startChromeDownload(options) {
    return new Promise((resolve, reject) => {
        chrome.downloads.download(options, (downloadId) => {
            const runtimeError = chrome.runtime.lastError;
            if (runtimeError) {
                reject(new Error(runtimeError.message));
                return;
            }

            if (typeof downloadId !== "number") {
                reject(new Error("O Chrome não retornou um identificador de download válido."));
                return;
            }

            resolve(downloadId);
        });
    });
}

async function handleStartDownload(payload) {
    await saveLastStatus({
        message: "Consultando API experimental...",
        tone: "neutral",
    });

    const responsePayload = await requestDirectDownload(payload.apiBaseUrl, payload);
    const resolvedLink = extractDownloadLink(responsePayload);
    const resolvedFileName = normalizeDownloadFilename(
        responsePayload.filename || responsePayload.output?.filename || "video",
        payload.videoFormat === "original" ? "" : payload.videoFormat,
    );

    const downloadId = await startChromeDownload({
        url: resolvedLink,
        filename: resolvedFileName,
        saveAs: true,
    });

    await saveLastStatus({
        message: "Download enviado ao Chrome.",
        tone: "success",
        downloadId,
    });

    return {
        ok: true,
        downloadId,
        message: "Download enviado ao Chrome.",
    };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type !== "start-download") {
        return undefined;
    }

    handleStartDownload(message.payload)
        .then((result) => {
            sendResponse(result);
        })
        .catch(async (error) => {
            const messageText = error instanceof Error
                ? error.message
                : "Não foi possível iniciar o download.";

            await saveLastStatus({
                message: messageText,
                tone: "danger",
            });

            sendResponse({
                ok: false,
                message: messageText,
            });
        });

    return true;
});
