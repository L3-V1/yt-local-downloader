import { DEFAULT_APP_URL, FALLBACK_APP_URLS } from "./constants.js";

export function normalizeAppBaseUrl(rawUrl) {
    const trimmedUrl = String(rawUrl || "").trim();
    const fallbackUrl = new URL(DEFAULT_APP_URL);

    try {
        const parsedUrl = new URL(trimmedUrl || DEFAULT_APP_URL);
        parsedUrl.hash = "";
        if (!parsedUrl.pathname.endsWith("/")) {
            parsedUrl.pathname = `${parsedUrl.pathname}/`;
        }
        return parsedUrl.toString();
    } catch (error) {
        return fallbackUrl.toString();
    }
}

export function buildApplicationUrlPatterns(configuredUrl) {
    const uniquePatterns = new Set(
        [configuredUrl, ...FALLBACK_APP_URLS.map((url) => normalizeAppBaseUrl(url))]
            .map((url) => `${normalizeAppBaseUrl(url)}*`)
    );
    return Array.from(uniquePatterns);
}

export function isSupportedYoutubeUrl(rawUrl) {
    try {
        const parsedUrl = new URL(rawUrl);
        const host = parsedUrl.hostname.toLowerCase();
        return [
            "www.youtube.com",
            "youtube.com",
            "m.youtube.com",
            "youtu.be",
        ].includes(host);
    } catch (error) {
        return false;
    }
}

export function buildAppSearchUrl(baseUrl, videoUrl) {
    const targetUrl = new URL(normalizeAppBaseUrl(baseUrl));
    targetUrl.searchParams.set("query", videoUrl);
    targetUrl.searchParams.set("source", "chrome-extension");
    return targetUrl.toString();
}
