(function initializeLibraryPage() {
    const librarySelectAll = document.getElementById("library-select-all");
    const librarySelectedCount = document.getElementById("library-selected-count");
    const libraryCheckboxes = Array.from(document.querySelectorAll(".library-video-checkbox"));
    const libraryBatchButtons = Array.from(document.querySelectorAll("[data-batch-action]"));
    const renameModal = document.getElementById("renameModal");
    const renameModalOverlay = document.getElementById("renameModalOverlay");
    const renameModalClose = document.getElementById("renameModalClose");
    const renameModalCancel = document.getElementById("renameModalCancel");
    const renameModalCurrentFileName = document.getElementById("renameModalCurrentFileName");
    const renameModalNewFileName = document.getElementById("renameModalNewFileName");
    const renameTriggers = Array.from(document.querySelectorAll("[data-rename-trigger]"));

    function syncLibrarySelectionState() {
        const selectedCount = libraryCheckboxes.filter((checkbox) => checkbox.checked).length;
        const allSelected = selectedCount > 0 && selectedCount === libraryCheckboxes.length;

        if (librarySelectedCount) {
            librarySelectedCount.textContent = String(selectedCount);
        }

        if (librarySelectAll) {
            librarySelectAll.checked = allSelected;
            librarySelectAll.indeterminate = selectedCount > 0 && !allSelected;
        }

        libraryBatchButtons.forEach((button) => {
            button.disabled = selectedCount === 0;
        });
    }

    function openRenameModal(fileName) {
        if (!renameModal || !renameModalCurrentFileName || !renameModalNewFileName) {
            return;
        }

        renameModalCurrentFileName.value = fileName;
        renameModalNewFileName.value = fileName;
        renameModal.classList.remove("hidden");
        document.body.classList.add("overflow-hidden");
        window.setTimeout(() => {
            renameModalNewFileName.focus();
            renameModalNewFileName.select();
        }, 0);
    }

    function closeRenameModal() {
        if (!renameModal) {
            return;
        }

        renameModal.classList.add("hidden");
        document.body.classList.remove("overflow-hidden");
    }

    function registerSelectionEvents() {
        librarySelectAll?.addEventListener("change", () => {
            libraryCheckboxes.forEach((checkbox) => {
                checkbox.checked = Boolean(librarySelectAll?.checked);
            });
            syncLibrarySelectionState();
        });

        libraryCheckboxes.forEach((checkbox) => {
            checkbox.addEventListener("change", syncLibrarySelectionState);
        });
    }

    function registerRenameEvents() {
        renameTriggers.forEach((trigger) => {
            trigger.addEventListener("click", () => {
                openRenameModal(trigger.dataset.fileName || "");
            });
        });

        renameModalOverlay?.addEventListener("click", closeRenameModal);
        renameModalClose?.addEventListener("click", closeRenameModal);
        renameModalCancel?.addEventListener("click", closeRenameModal);

        window.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeRenameModal();
            }
        });
    }

    if (!libraryCheckboxes.length) {
        return;
    }

    registerSelectionEvents();
    registerRenameEvents();
    syncLibrarySelectionState();
})();
