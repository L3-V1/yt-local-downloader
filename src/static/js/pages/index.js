(function initializeSearchPage() {
    const downloadModal = document.getElementById("downloadModal");
    const downloadModalOverlay = document.getElementById("downloadModalOverlay");
    const downloadModalClose = document.getElementById("downloadModalClose");
    const downloadModalCancel = document.getElementById("downloadModalCancel");
    const downloadModalTitle = document.getElementById("downloadModalTitle");
    const downloadModalUrl = document.getElementById("downloadModalUrl");
    const downloadModalForm = document.getElementById("downloadModalForm");
    const downloadModalSubmit = document.getElementById("downloadModalSubmit");
    const downloadModalSubmitLabel = document.getElementById("downloadModalSubmitLabel");
    const downloadToastStack = document.getElementById("downloadToastStack");
    const downloadTriggers = Array.from(document.querySelectorAll("[data-download-trigger]"));
    const searchQueryInput = document.getElementById("query");
    let isDownloadSubmitting = false;

    function syncSearchFieldFromUrl() {
        if (!searchQueryInput) {
            return;
        }

        const currentUrl = new URL(window.location.href);
        const queryFromUrl = currentUrl.searchParams.get("query");
        if (!queryFromUrl) {
            return;
        }

        searchQueryInput.value = queryFromUrl;
    }

    function openDownloadModal(videoUrl, videoTitle) {
        if (!downloadModal || !downloadModalUrl || !downloadModalTitle) {
            return;
        }

        downloadModalUrl.value = videoUrl;
        downloadModalTitle.textContent = videoTitle;
        downloadModal.classList.remove("hidden");
        document.body.classList.add("overflow-hidden");
    }

    function hideDownloadModal() {
        if (!downloadModal) {
            return;
        }

        downloadModal.classList.add("hidden");
        document.body.classList.remove("overflow-hidden");
    }

    function closeDownloadModal() {
        if (isDownloadSubmitting) {
            return;
        }

        hideDownloadModal();
    }

    function setDownloadSubmittingState(isSubmitting) {
        isDownloadSubmitting = isSubmitting;

        if (downloadModalSubmit) {
            downloadModalSubmit.disabled = isSubmitting;
        }

        if (downloadModalSubmitLabel) {
            downloadModalSubmitLabel.textContent = isSubmitting ? "Enviando..." : "Confirmar download";
        }
    }

    function buildToastClasses(level) {
        if (level === "success") {
            return "border-emerald-500/30 bg-emerald-500/10 text-emerald-100";
        }
        if (level === "warning") {
            return "border-yellow-500/30 bg-yellow-500/10 text-yellow-100";
        }
        return "border-yt-red/30 bg-yt-red/10 text-red-100";
    }

    function buildToastIcon(level) {
        if (level === "success") {
            return '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m5 12 5 5L20 7"></path></svg>';
        }
        if (level === "warning") {
            return '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 9v4"></path><path d="M12 17h.01"></path><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"></path></svg>';
        }
        return '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 9v4"></path><path d="M12 17h.01"></path><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"></path></svg>';
    }

    function removeToast(toast) {
        toast.classList.add("translate-y-2", "opacity-0");
        window.setTimeout(() => toast.remove(), 200);
    }

    function showDownloadToast(message, level) {
        if (!downloadToastStack) {
            return;
        }

        const toast = document.createElement("div");
        toast.className = `pointer-events-auto overflow-hidden rounded-[1.5rem] border px-4 py-4 shadow-card backdrop-blur transition duration-300 ${buildToastClasses(level || "success")}`;
        toast.innerHTML = `
            <div class="flex items-start gap-3">
                <span class="mt-0.5 inline-flex h-10 w-10 flex-none items-center justify-center rounded-2xl bg-black/10 text-current">
                    ${buildToastIcon(level || "success")}
                </span>
                <div class="min-w-0 flex-1">
                    <p class="text-sm font-semibold uppercase tracking-[0.18em]">${level === "success" ? "Sucesso" : level === "warning" ? "Atenção" : "Erro"}</p>
                    <p class="mt-1 text-sm leading-6">${message}</p>
                </div>
                <button type="button" class="inline-flex h-10 w-10 flex-none items-center justify-center rounded-2xl border border-white/10 bg-black/10 text-current transition hover:bg-white/10" aria-label="Fechar aviso">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                        <path d="m6 6 12 12"></path>
                        <path d="M18 6 6 18"></path>
                    </svg>
                </button>
            </div>
        `;

        const dismissButton = toast.querySelector("button");
        dismissButton?.addEventListener("click", () => removeToast(toast));
        downloadToastStack.prepend(toast);
        window.setTimeout(() => removeToast(toast), 4500);
    }

    async function submitDownloadForm(event) {
        event.preventDefault();
        if (!downloadModalForm || isDownloadSubmitting) {
            return;
        }

        if (!downloadModalUrl || !downloadModalUrl.value.trim()) {
            showDownloadToast("Selecione um vídeo antes de confirmar o download.", "error");
            return;
        }

        setDownloadSubmittingState(true);

        try {
            const response = await fetch(downloadModalForm.action, {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: new FormData(downloadModalForm),
            });

            const payload = await response.json();
            showDownloadToast(payload.message || "Não foi possível processar o download.", payload.level || "error");

            if (payload.success) {
                hideDownloadModal();
            }
        } catch (error) {
            showDownloadToast("Não foi possível enviar o download agora. Tente novamente em instantes.", "error");
        } finally {
            setDownloadSubmittingState(false);
        }
    }

    function registerDownloadTriggers() {
        downloadTriggers.forEach((trigger) => {
            trigger.addEventListener("click", () => {
                openDownloadModal(trigger.dataset.videoUrl || "", trigger.dataset.videoTitle || "");
            });
        });
    }

    function registerModalEvents() {
        downloadModalForm?.addEventListener("submit", submitDownloadForm);
        downloadModalOverlay?.addEventListener("click", closeDownloadModal);
        downloadModalClose?.addEventListener("click", closeDownloadModal);
        downloadModalCancel?.addEventListener("click", closeDownloadModal);
        window.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeDownloadModal();
            }
        });
    }

    syncSearchFieldFromUrl();
    registerDownloadTriggers();
    registerModalEvents();
})();
