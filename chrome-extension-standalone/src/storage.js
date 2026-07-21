import {
    API_URL_STORAGE_KEY,
    DEFAULT_API_URL,
    DEFAULT_VIDEO_FORMAT,
    DEFAULT_VIDEO_QUALITY,
    DOWNLOAD_FORMAT_STORAGE_KEY,
    DOWNLOAD_QUALITY_STORAGE_KEY,
    LEGACY_DEFAULT_API_URL,
    LAST_STATUS_STORAGE_KEY,
} from "./constants.js";
import { normalizeApiBaseUrl } from "./url.js";

function resolveStoredApiUrl(storedApiUrl) {
    const normalizedStoredApiUrl = normalizeApiBaseUrl(storedApiUrl || DEFAULT_API_URL);

    if (normalizedStoredApiUrl === normalizeApiBaseUrl(LEGACY_DEFAULT_API_URL)) {
        return normalizeApiBaseUrl(DEFAULT_API_URL);
    }

    return normalizedStoredApiUrl;
}

export async function loadSavedSettings() {
    const storedSettings = await chrome.storage.sync.get([
        API_URL_STORAGE_KEY,
        DOWNLOAD_FORMAT_STORAGE_KEY,
        DOWNLOAD_QUALITY_STORAGE_KEY,
    ]);
    const storedRuntimeState = await chrome.storage.local.get([LAST_STATUS_STORAGE_KEY]);

    return {
        apiBaseUrl: resolveStoredApiUrl(storedSettings[API_URL_STORAGE_KEY]),
        videoFormat: String(storedSettings[DOWNLOAD_FORMAT_STORAGE_KEY] || DEFAULT_VIDEO_FORMAT),
        videoQuality: String(storedSettings[DOWNLOAD_QUALITY_STORAGE_KEY] || DEFAULT_VIDEO_QUALITY),
        lastStatus: storedRuntimeState[LAST_STATUS_STORAGE_KEY] || null,
    };
}

export async function saveApiUrl(rawUrl) {
    const normalizedUrl = normalizeApiBaseUrl(rawUrl);
    await chrome.storage.sync.set({
        [API_URL_STORAGE_KEY]: normalizedUrl,
    });
    return normalizedUrl;
}

export async function saveDownloadPreferences(videoFormat, videoQuality) {
    await chrome.storage.sync.set({
        [DOWNLOAD_FORMAT_STORAGE_KEY]: String(videoFormat || DEFAULT_VIDEO_FORMAT),
        [DOWNLOAD_QUALITY_STORAGE_KEY]: String(videoQuality || DEFAULT_VIDEO_QUALITY),
    });
}

export async function saveLastStatus(status) {
    await chrome.storage.local.set({
        [LAST_STATUS_STORAGE_KEY]: status,
    });
}
