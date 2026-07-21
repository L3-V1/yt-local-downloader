import test from "node:test";
import assert from "node:assert/strict";

import { buildApiPayload, requestDirectDownload } from "../src/api.js";

test("buildApiPayload converte qualidade best para max", () => {
    assert.deepEqual(
        buildApiPayload({
            videoUrl: "https://www.youtube.com/watch?v=abc123",
            videoFormat: "mp4",
            videoQuality: "best",
        }),
        {
            url: "https://www.youtube.com/watch?v=abc123",
            filenameStyle: "basic",
            youtubeVideoCodec: "h264",
            localProcessing: "disabled",
            videoQuality: "max",
            youtubeVideoContainer: "mp4",
        },
    );
});

test("buildApiPayload usa container auto no formato original", () => {
    assert.deepEqual(
        buildApiPayload({
            videoUrl: "https://www.youtube.com/watch?v=abc123",
            videoFormat: "original",
            videoQuality: "1080",
        }),
        {
            url: "https://www.youtube.com/watch?v=abc123",
            filenameStyle: "basic",
            youtubeVideoCodec: "h264",
            localProcessing: "disabled",
            videoQuality: "1080",
            youtubeVideoContainer: "auto",
        },
    );
});

test("requestDirectDownload retorna o payload JSON da API", async () => {
    const originalFetch = global.fetch;

    global.fetch = async (requestUrl, requestOptions) => {
        assert.equal(requestUrl, "https://api.cobalt.liubquanti.click/");
        assert.equal(requestOptions.method, "POST");

        return new Response(
            JSON.stringify({
                status: "redirect",
                url: "https://downloads.example/video.mp4",
                filename: "video.mp4",
            }),
            {
                status: 200,
                headers: {
                    "Content-Type": "application/json",
                },
            },
        );
    };

    try {
        const responsePayload = await requestDirectDownload("https://api.cobalt.liubquanti.click/", {
            videoUrl: "https://www.youtube.com/watch?v=abc123",
            videoFormat: "mp4",
            videoQuality: "best",
        });

        assert.equal(responsePayload.status, "redirect");
        assert.equal(responsePayload.filename, "video.mp4");
        assert.equal(responsePayload.resolvedApiBaseUrl, "https://api.cobalt.liubquanti.click/");
    } finally {
        global.fetch = originalFetch;
    }
});

test("requestDirectDownload propaga erros textuais quando a API falha", async () => {
    const originalFetch = global.fetch;

    global.fetch = async () => new Response("Protegido por anti-bot", {
        status: 403,
        headers: {
            "Content-Type": "text/plain",
        },
    });

    try {
        await assert.rejects(
            requestDirectDownload("https://api.cobalt.liubquanti.click/", {
                videoUrl: "https://www.youtube.com/watch?v=abc123",
                videoFormat: "mp4",
                videoQuality: "best",
            }),
            /Protegido por anti-bot/,
        );
    } finally {
        global.fetch = originalFetch;
    }
});

test("requestDirectDownload tenta outra instância quando a principal falha", async () => {
    const originalFetch = global.fetch;
    const visitedUrls = [];

    global.fetch = async (requestUrl) => {
        visitedUrls.push(requestUrl);

        if (requestUrl === "https://api.cobalt.liubquanti.click/") {
            return new Response(JSON.stringify({ text: "A API experimental recusou a solicitação." }), {
                status: 403,
                headers: {
                    "Content-Type": "application/json",
                },
            });
        }

        return new Response(JSON.stringify({
            status: "redirect",
            url: "https://downloads.example/video.mp4",
            filename: "video.mp4",
        }), {
            status: 200,
            headers: {
                "Content-Type": "application/json",
            },
        });
    };

    try {
        const responsePayload = await requestDirectDownload("https://api.cobalt.liubquanti.click/", {
            videoUrl: "https://www.youtube.com/watch?v=abc123",
            videoFormat: "mp4",
            videoQuality: "best",
        });

        assert.equal(visitedUrls[0], "https://api.cobalt.liubquanti.click/");
        assert.equal(visitedUrls[1], "https://subito-c.meowing.de/");
        assert.equal(responsePayload.resolvedApiBaseUrl, "https://subito-c.meowing.de/");
    } finally {
        global.fetch = originalFetch;
    }
});
