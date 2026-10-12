// Interactions légères de l'interface NAMARA.
document.addEventListener("DOMContentLoaded", function () {
    const SPINNER = '<span class="btn-spinner" aria-hidden="true"></span>';

    // Affiche un loader (spinner) sur un bouton/lien d'action.
    function showLoader(el, label) {
        if (el.classList.contains("is-loading")) return;
        el.classList.add("is-loading");
        el.setAttribute("aria-busy", "true");
        el.innerHTML = SPINNER + " " + (label || "Traitement…");
    }

    // Boutons de soumission de formulaire (avec ou sans type="submit").
    // Anti double-soumission + loader.
    document.querySelectorAll("form").forEach(function (form) {
        form.addEventListener("submit", function () {
            form.querySelectorAll("button[type=submit], button:not([type])").forEach(function (btn) {
                if (btn.disabled) return;
                btn.disabled = true;
                showLoader(btn, "Traitement…");
            });
        });
    });

    // Boutons d'action de type lien (ex. « Investir » sur la page produits).
    document.querySelectorAll("a.prd-btn--primary").forEach(function (link) {
        link.addEventListener("click", function () {
            if (link.classList.contains("is-loading")) return;
            showLoader(link, link.textContent.trim());
        });
    });
});
