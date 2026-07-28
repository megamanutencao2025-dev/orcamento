(() => {
    const root = document.documentElement;
    const themeButton = document.querySelector("#theme-toggle");
    const themeMeta = document.querySelector('meta[name="theme-color"]');

    function setTheme(theme) {
        const normalized = theme === "dark" ? "dark" : "light";
        root.dataset.theme = normalized;
        localStorage.setItem("pricewise-theme", normalized);
        if (themeButton) {
            const isDark = normalized === "dark";
            themeButton.setAttribute("aria-pressed", String(isDark));
            themeButton.setAttribute(
                "aria-label",
                isDark ? "Ativar tema claro" : "Ativar tema escuro",
            );
        }
        if (themeMeta) {
            themeMeta.content = normalized === "dark" ? "#0b1420" : "#f5f7fb";
        }
        window.dispatchEvent(
            new CustomEvent("pricewise:themechange", { detail: { theme: normalized } }),
        );
    }

    window.PriceTracker = { setTheme };
    setTheme(root.dataset.theme);

    themeButton?.addEventListener("click", () => {
        setTheme(root.dataset.theme === "dark" ? "light" : "dark");
    });

    const menuButton = document.querySelector("#menu-toggle");
    const backdrop = document.querySelector("#sidebar-backdrop");
    const closeMenu = () => document.body.classList.remove("sidebar-open");
    menuButton?.addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
    backdrop?.addEventListener("click", closeMenu);
    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenu();
    });

    document.querySelectorAll("form[data-confirm]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!window.confirm(form.dataset.confirm)) event.preventDefault();
        });
    });
})();
