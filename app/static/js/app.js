// Interactions légères de l'interface NAMARA.
document.addEventListener("DOMContentLoaded", function () {
    // Désactivation du bouton après soumission (anti double-soumission).
    document.querySelectorAll("form").forEach(function (form) {
        form.addEventListener("submit", function () {
            const btn = form.querySelector("button[type=submit]");
            if (btn) {
                btn.disabled = true;
                btn.textContent = "Traitement…";
            }
        });
    });
});
