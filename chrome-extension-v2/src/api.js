import { FALLBACK_API_URLS } from "./constants.js";
import { buildApiRequestUrl, normalizeApiBaseUrl } from "./url.js";

export function buildApiPayload(payload) {
    const requestPayload = {
        url: payload.videoUrl,
        filenameStyle: "basic",
        youtubeVideoCodec: "h264",
        localProcessing: "disabled",
    };

    if (payload.videoFormat === "original") {
        requestPayload.videoQuality = payload.videoQuality === "best" ? "max" : payload.videoQuality;
        requestPayload.youtubeVideoContainer = "auto";
        return requestPayload;
    }

    requestPayload.videoQuality = payload.videoQuality === "best" ? "max" : payload.videoQuality;
    requestPayload.youtubeVideoContainer = payload.videoFormat;
    return requestPayload;
}

async function parseApiResponse(response) {
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
        return response.json();
    }

    const responseText = await response.text();
    return {
        text: responseText,
    };
}

function buildRequestCandidates(baseUrl) {
    const normalizedPrimaryUrl = normalizeApiBaseUrl(baseUrl);
    const allCandidates = [normalizedPrimaryUrl, ...FALLBACK_API_URLS.map((url) => normalizeApiBaseUrl(url))];
    return Array.from(new Set(allCandidates));
}

function extractApiErrorMessage(responsePayload) {
    if (typeof responsePayload?.text === "string" && responsePayload.text.trim()) {
        return responsePayload.text.trim();
    }

    return "A API experimental recusou a solicitação.";
}

async function performDirectDownloadRequest(baseUrl, payload) {
    const response = await fetch(buildApiRequestUrl(baseUrl), {
        method: "POST",
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(buildApiPayload(payload)),
    });

    const responsePayload = await parseApiResponse(response);
    if (!response.ok) {
        throw new Error(extractApiErrorMessage(responsePayload));
    }

    return responsePayload;
}

function shouldTryNextApi(error) {
    if (!(error instanceof Error)) {
        return true;
    }

    const errorMessage = error.message.toLowerCase();
    return [
        "recusou a solicitação",
        "disabled_main_instance",
        "youtube disabled",
        "youtube login",
        "login required",
        "forbidden",
        "429",
        "403",
        "failed to fetch",
        "networkerror",
    ].some((pattern) => errorMessage.includes(pattern));
}

export async function requestDirectDownload(baseUrl, payload) {
    const requestCandidates = buildRequestCandidates(baseUrl);
    let lastError = null;

    for (const requestBaseUrl of requestCandidates) {
        try {
            const responsePayload = await performDirectDownloadRequest(requestBaseUrl, payload);
            return {
                ...responsePayload,
                resolvedApiBaseUrl: requestBaseUrl,
            };
        } catch (error) {
            lastError = error;
            if (!shouldTryNextApi(error)) {
                throw error;
            }
        }
    }

    throw lastError || new Error("Nenhuma API pública disponível aceitou a solicitação.");
}
