import { DEFAULT_API_URL } from "./constants.js";

export function normalizeApiBaseUrl(rawUrl) {
    const trimmedUrl = String(rawUrl || "").trim();
    const fallbackUrl = new URL(DEFAULT_API_URL);

    try {
        const parsedUrl = new URL(trimmedUrl || DEFAULT_API_URL);
        parsedUrl.hash = "";
        if (!parsedUrl.pathname.endsWith("/")) {
            parsedUrl.pathname = `${parsedUrl.pathname}/`;
        }
        return parsedUrl.toString();
    } catch (error) {
        return fallbackUrl.toString();
    }
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

export function buildApiRequestUrl(baseUrl) {
    return new URL("/", normalizeApiBaseUrl(baseUrl)).toString();
}

export function sanitizeDownloadFileName(rawFileName) {
    return String(rawFileName || "")
        .split(/[\\/]/)
        .filter(Boolean)
        .pop() || "video.mp4";
}

export function normalizeDownloadFilename(rawFileName, fallbackExtension) {
    const sanitizedFileName = sanitizeDownloadFileName(rawFileName);
    if (sanitizedFileName.includes(".")) {
        return sanitizedFileName;
    }

    const normalizedExtension = String(fallbackExtension || "").replace(/^\./, "").trim();
    if (!normalizedExtension) {
        return sanitizedFileName;
    }

    return `${sanitizedFileName}.${normalizedExtension}`;
}
