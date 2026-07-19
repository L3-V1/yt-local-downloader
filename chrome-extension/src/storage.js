import { APP_URL_STORAGE_KEY, DEFAULT_APP_URL } from "./constants.js";
import { normalizeAppBaseUrl } from "./url.js";

export async function loadSavedAppUrl() {
    const result = await chrome.storage.sync.get(APP_URL_STORAGE_KEY);
    return normalizeAppBaseUrl(result[APP_URL_STORAGE_KEY] || DEFAULT_APP_URL);
}

export async function saveAppUrl(rawUrl) {
    const normalizedUrl = normalizeAppBaseUrl(rawUrl);
    await chrome.storage.sync.set({
        [APP_URL_STORAGE_KEY]: normalizedUrl,
    });
    return normalizedUrl;
}
