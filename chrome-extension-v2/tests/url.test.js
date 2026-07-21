import test from "node:test";
import assert from "node:assert/strict";

import {
    buildApiRequestUrl,
    isSupportedYoutubeUrl,
    normalizeApiBaseUrl,
    normalizeDownloadFilename,
    sanitizeDownloadFileName,
} from "../src/url.js";

test("normalizeApiBaseUrl mantém barra final e remove hash", () => {
    assert.equal(
        normalizeApiBaseUrl("https://api.cobalt.tools/api#teste"),
        "https://api.cobalt.tools/api/",
    );
});

test("isSupportedYoutubeUrl aceita links válidos do YouTube", () => {
    assert.equal(isSupportedYoutubeUrl("https://www.youtube.com/watch?v=abc123"), true);
    assert.equal(isSupportedYoutubeUrl("https://youtu.be/abc123"), true);
});

test("sanitizeDownloadFileName remove caminhos do nome do arquivo", () => {
    assert.equal(sanitizeDownloadFileName("pastas/video.mp4"), "video.mp4");
    assert.equal(sanitizeDownloadFileName("pastas\\video.mp4"), "video.mp4");
});

test("buildApiRequestUrl resolve para a raiz da API", () => {
    assert.equal(
        buildApiRequestUrl("https://api.cobalt.tools/api/"),
        "https://api.cobalt.tools/",
    );
});

test("normalizeDownloadFilename adiciona extensão quando necessário", () => {
    assert.equal(normalizeDownloadFilename("video-final", "mp4"), "video-final.mp4");
    assert.equal(normalizeDownloadFilename("video-final.webm", "mp4"), "video-final.webm");
});

test("normalizeDownloadFilename mantém nome sem extensão quando não há fallback", () => {
    assert.equal(normalizeDownloadFilename("video-final", ""), "video-final");
});
