// Interactions légères de l'interface NAMARA.

// Popup Telegram NAMARA : affiché à chaque visite du tableau de bord,
// sans mémorisation (aucun localStorage/sessionStorage/cookie).
function initNamaraTelegramModal() {
    var modal = document.getElementById("namaraTelegramModal");
    if (!modal) return;

    var isOpen = false;
    var lastFocused = null;
    var focusable = modal.querySelectorAll("a[href], button:not([disabled])");

    function openModal() {
        if (isOpen) return;
        isOpen = true;
        lastFocused = document.activeElement;
        document.body.classList.add("namara-modal-open");
        modal.setAttribute("aria-hidden", "false");
        // Déclenche l'animation d'apparition (fondu + zoom) au frame suivant.
        requestAnimationFrame(function () {
            modal.classList.add("is-open");
        });
        if (focusable.length) focusable[0].focus();
    }

    function closeModal() {
        if (!isOpen) return;
        isOpen = false;
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("namara-modal-open");
        if (lastFocused && lastFocused.focus) lastFocused.focus();
    }

    // Fermeture : croix, bouton « Plus tard » et clic sur le fond assombri.
    modal.querySelectorAll("[data-namara-telegram-close]").forEach(function (el) {
        el.addEventListener("click", closeModal);
    });

    // Un clic à l'intérieur de la carte ne ferme jamais le popup.
    var card = modal.querySelector(".namara-telegram-modal__card");
    if (card) {
        card.addEventListener("click", function (e) {
            e.stopPropagation();
        });
    }

    // Fermeture avec la touche Échap.
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && isOpen) closeModal();
    });

    // Apparition après le chargement du dashboard (petit délai + animation).
    setTimeout(openModal, 350);
}

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

    initNamaraTelegramModal();
});
