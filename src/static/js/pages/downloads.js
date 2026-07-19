(function initializeDownloadsPage() {
    const downloadsStorageKey = "youtube-local-downloader-history";
    const downloadsPayloadElement = document.getElementById("downloadsPayload");
    const downloadsListElement = document.getElementById("downloadsList");
    const downloadsEmptyStateElement = document.getElementById("downloadsEmptyState");
    const downloadsMenuButton = document.getElementById("downloadsMenuButton");
    const downloadsMenu = document.getElementById("downloadsMenu");
    const downloadsMenuWrapper = document.getElementById("downloadsMenuWrapper");
    const clearAllDownloadsForm = document.getElementById("clearAllDownloadsForm");
    const downloadsRefreshButton = document.getElementById("downloadsRefreshButton");
    const downloadsStatusEndpoint = "/downloads/status";
    const downloadsPollingIntervalMs = 1500;
    let durationTimer = null;
    let downloadsPollingTimer = null;
    let isPollingDownloads = false;

    function loadServerDownloads() {
        if (!downloadsPayloadElement) {
            return [];
        }

        try {
            return JSON.parse(downloadsPayloadElement.textContent || "[]");
        } catch (error) {
            return [];
        }
    }

    function loadStoredDownloads() {
        try {
            return JSON.parse(localStorage.getItem(downloadsStorageKey) || "[]");
        } catch (error) {
            return [];
        }
    }

    function saveStoredDownloads(items) {
        localStorage.setItem(downloadsStorageKey, JSON.stringify(items));
    }

    function mergeDownloads(existingItems, incomingItems) {
        const itemsById = new Map();
        existingItems.forEach((item) => itemsById.set(item.id, item));
        incomingItems.forEach((item) => itemsById.set(item.id, item));

        return Array.from(itemsById.values()).sort((left, right) => {
            return right.created_at_display.localeCompare(left.created_at_display);
        });
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function buildStatusClass(status) {
        if (status === "Concluido") {
            return "bg-emerald-500/15 text-emerald-300";
        }
        if (status === "Erro") {
            return "bg-red-500/15 text-red-300";
        }
        return "bg-yellow-500/15 text-yellow-200";
    }

    function buildStatusLabel(status) {
        if (status === "Concluido") {
            return "Concluído";
        }
        if (status === "Em andamento") {
            return "Em andamento";
        }
        if (status === "Erro") {
            return "Erro";
        }
        return status;
    }

    function buildProgressBarClass(status) {
        if (status === "Concluido") {
            return "bg-emerald-400";
        }
        if (status === "Erro") {
            return "bg-red-400";
        }
        return "bg-yt-red";
    }

    function buildMetaText(item) {
        const parts = [];
        if (item.speed_text) {
            parts.push(`Velocidade: ${escapeHtml(item.speed_text)}`);
        }
        if (item.eta_text && item.status === "Em andamento") {
            parts.push(`ETA: ${escapeHtml(item.eta_text)}`);
        }
        return parts.join(" • ");
    }

    function formatDuration(totalSeconds) {
        const seconds = Math.max(0, Math.floor(totalSeconds));
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainingSeconds = seconds % 60;

        if (hours > 0) {
            return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
        }

        return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
    }

    function updateDurationFields() {
        const durationElements = document.querySelectorAll("[data-download-duration]");
        const now = Date.now();

        durationElements.forEach((element) => {
            const createdAtRaw = element.getAttribute("data-created-at");
            const finishedAtRaw = element.getAttribute("data-finished-at");
            if (!createdAtRaw) {
                element.textContent = "--:--";
                return;
            }

            const createdAt = Date.parse(createdAtRaw);
            const finishedAt = finishedAtRaw ? Date.parse(finishedAtRaw) : now;
            if (Number.isNaN(createdAt) || Number.isNaN(finishedAt)) {
                element.textContent = "--:--";
                return;
            }

            element.textContent = formatDuration((finishedAt - createdAt) / 1000);
        });
    }

    function startDurationTimer() {
        if (durationTimer) {
            window.clearInterval(durationTimer);
        }

        updateDurationFields();
        durationTimer = window.setInterval(updateDurationFields, 1000);
    }

    function bindDeleteForms() {
        document.querySelectorAll("[data-download-delete-form]").forEach((form) => {
            form.addEventListener("submit", () => {
                const article = form.closest("[data-download-id]");
                const downloadId = article?.getAttribute("data-download-id");
                if (!downloadId) {
                    return;
                }

                const filteredItems = loadStoredDownloads().filter((item) => item.id !== downloadId);
                saveStoredDownloads(filteredItems);
            });
        });
    }

    function renderDownloads(items) {
        if (!downloadsListElement || !downloadsEmptyStateElement) {
            return;
        }

        if (!items.length) {
            downloadsListElement.innerHTML = "";
            downloadsEmptyStateElement.classList.remove("hidden");
            return;
        }

        downloadsEmptyStateElement.classList.add("hidden");
        downloadsListElement.innerHTML = items.map((item) => {
            const metaText = buildMetaText(item);
            const progressPercent = Number(item.progress_percent || 0);
            const isRetryVisible = item.status === "Erro";

            return `
                <article class="grid gap-5 px-5 py-5 xl:grid-cols-[minmax(0,1.8fr)_minmax(320px,1fr)_minmax(220px,auto)] xl:items-center xl:gap-6 md:px-6" data-download-id="${escapeHtml(item.id)}">
                    <div class="min-w-0 space-y-3">
                        <div class="flex flex-wrap items-center justify-between gap-3">
                            <div class="flex flex-wrap items-center gap-3">
                                <span class="inline-flex rounded-full px-3 py-1 text-sm font-semibold ${buildStatusClass(item.status)}">
                                    ${escapeHtml(buildStatusLabel(item.status))}
                                </span>
                                <p class="text-xs uppercase tracking-[0.2em] text-[#8a8a8a]">Criado em ${escapeHtml(item.created_at_display)}</p>
                            </div>
                            ${isRetryVisible ? `
                            <form action="/downloads/${encodeURIComponent(item.id)}/retry" method="post">
                                <button
                                    type="submit"
                                    class="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-yt-red/30 bg-yt-red/10 text-red-100 transition hover:bg-yt-red/20"
                                    aria-label="Tentar novamente"
                                    title="Tentar novamente"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                                        <path d="M21 12a9 9 0 1 1-2.64-6.36"></path>
                                        <path d="M21 3v6h-6"></path>
                                    </svg>
                                </button>
                            </form>
                            ` : ""}
                        </div>

                        <a href="${escapeHtml(item.video_url)}" target="_blank" rel="noopener noreferrer" class="inline-block break-all text-sm font-semibold text-white hover:text-red-200">
                            ${escapeHtml(item.video_url)}
                        </a>

                        <div class="space-y-2">
                            <div class="h-2.5 overflow-hidden rounded-full bg-white/10">
                                <div class="h-full rounded-full transition-all duration-300 ${buildProgressBarClass(item.status)}" style="width:${Math.max(0, Math.min(100, progressPercent))}%"></div>
                            </div>
                            <div class="flex flex-wrap items-center justify-between gap-3">
                                <p class="text-sm text-[#d7d7d7]">${escapeHtml(item.progress_text || "Aguardando início")}</p>
                                <p class="text-sm font-semibold text-white">${escapeHtml(progressPercent.toFixed(1))}%</p>
                            </div>
                            ${metaText ? `<p class="text-xs text-[#9f9f9f]">${metaText}</p>` : ""}
                        </div>
                    </div>

                    <div class="rounded-2xl bg-[#212121] p-4">
                        <div class="flex flex-wrap items-center justify-center gap-8 text-center">
                            <div class="min-w-[96px]">
                                <p class="text-xs uppercase tracking-[0.2em] text-[#8a8a8a]">Duração</p>
                                <p class="mt-2 text-sm font-semibold text-white" data-download-duration data-created-at="${escapeHtml(item.created_at_iso || "")}" data-finished-at="${escapeHtml(item.finished_at_iso || "")}">
                                    --:--
                                </p>
                            </div>
                            <div class="min-w-[96px]">
                                <p class="text-xs uppercase tracking-[0.2em] text-[#8a8a8a]">Formato</p>
                                <p class="mt-2 text-sm font-semibold text-white">${escapeHtml(String(item.video_format || "").toUpperCase() || "N/D")}</p>
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-col gap-3 xl:items-center xl:justify-center">
                        <div class="flex w-full flex-col gap-3 sm:flex-row xl:w-auto xl:min-w-[170px] xl:flex-col">
                            <form action="/downloads/${encodeURIComponent(item.id)}/delete" method="post" data-download-delete-form class="w-full">
                                <button type="submit" class="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-red-900/60 bg-red-950/50 px-4 py-3 text-sm font-semibold text-red-100 transition hover:bg-red-950/80 sm:min-w-[170px]">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                                        <path d="M3 6h18"></path>
                                        <path d="M8 6V4h8v2"></path>
                                        <path d="m19 6-1 14H6L5 6"></path>
                                        <path d="M10 11v6"></path>
                                        <path d="M14 11v6"></path>
                                    </svg>
                                    Remover
                                </button>
                            </form>
                        </div>
                    </div>
                </article>
            `;
        }).join("");

        bindDeleteForms();
        startDurationTimer();
    }

    function initializeDownloadsHistory() {
        const mergedItems = mergeDownloads(loadStoredDownloads(), loadServerDownloads());
        saveStoredDownloads(mergedItems);
        renderDownloads(mergedItems);
    }

    async function refreshDownloadsHistory() {
        if (isPollingDownloads) {
            return;
        }

        isPollingDownloads = true;

        try {
            const response = await fetch(downloadsStatusEndpoint, {
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                cache: "no-store",
            });

            if (!response.ok) {
                return;
            }

            const payload = await response.json();
            const latestItems = Array.isArray(payload.downloads) ? payload.downloads : [];
            const mergedItems = mergeDownloads(loadStoredDownloads(), latestItems);
            saveStoredDownloads(mergedItems);
            renderDownloads(mergedItems);
        } catch (error) {
            console.error("Nao foi possivel atualizar o progresso dos downloads em tempo real.", error);
        } finally {
            isPollingDownloads = false;
        }
    }

    function startDownloadsPolling() {
        if (downloadsPollingTimer) {
            window.clearInterval(downloadsPollingTimer);
        }

        downloadsPollingTimer = window.setInterval(refreshDownloadsHistory, downloadsPollingIntervalMs);
    }

    function toggleDownloadsMenu() {
        if (!downloadsMenu) {
            return;
        }

        downloadsMenu.classList.toggle("hidden");
    }

    function registerPageEvents() {
        downloadsRefreshButton?.addEventListener("click", async () => {
            await refreshDownloadsHistory();
        });

        if (downloadsMenuButton && downloadsMenu) {
            downloadsMenuButton.addEventListener("click", toggleDownloadsMenu);
            document.addEventListener("click", (event) => {
                if (!downloadsMenuWrapper?.contains(event.target)) {
                    downloadsMenu.classList.add("hidden");
                }
            });
        }

        clearAllDownloadsForm?.addEventListener("submit", () => {
            localStorage.removeItem(downloadsStorageKey);
        });
    }

    initializeDownloadsHistory();
    registerPageEvents();
    startDownloadsPolling();
})();
