(function initializeLayout() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");
    const menuButton = document.getElementById("menuButton");

    function openSidebar() {
        if (!sidebar || !overlay) {
            return;
        }

        sidebar.classList.remove("-translate-x-full");
        overlay.classList.remove("hidden");
        document.body.classList.add("overflow-hidden");
    }

    function closeSidebar() {
        if (!sidebar || !overlay) {
            return;
        }

        sidebar.classList.add("-translate-x-full");
        overlay.classList.add("hidden");
        document.body.classList.remove("overflow-hidden");
    }

    function toggleSidebar() {
        if (!sidebar) {
            return;
        }

        if (sidebar.classList.contains("-translate-x-full")) {
            openSidebar();
            return;
        }

        closeSidebar();
    }

    function handleResize() {
        if (!overlay || window.innerWidth < 768) {
            return;
        }

        overlay.classList.add("hidden");
        document.body.classList.remove("overflow-hidden");
    }

    if (!menuButton || !overlay || !sidebar) {
        return;
    }

    menuButton.addEventListener("click", toggleSidebar);
    overlay.addEventListener("click", closeSidebar);
    window.addEventListener("resize", handleResize);
})();
