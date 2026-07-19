(function initializeFlashMessage() {
    const flashMessage = document.getElementById("flashMessage");
    const flashMessageDismiss = document.getElementById("flashMessageDismiss");

    function clearFlashQueryParams() {
        const currentUrl = new URL(window.location.href);
        if (!currentUrl.searchParams.has("flash_message") && !currentUrl.searchParams.has("flash_level")) {
            return;
        }

        currentUrl.searchParams.delete("flash_message");
        currentUrl.searchParams.delete("flash_level");
        const nextUrl = `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`;
        window.history.replaceState({}, document.title, nextUrl);
    }

    if (flashMessage) {
        clearFlashQueryParams();
    }

    if (!flashMessage || !flashMessageDismiss) {
        return;
    }

    flashMessageDismiss.addEventListener("click", () => {
        flashMessage.remove();
    });
})();
