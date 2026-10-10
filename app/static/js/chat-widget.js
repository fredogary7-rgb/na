(function () {
    "use strict";
    var BASE = "/support/api";
    var CATEGORIES = [
        { key: "account", label: "Problème de compte" },
        { key: "deposit", label: "Dépôt" },
        { key: "withdrawal", label: "Retrait" },
        { key: "products", label: "Produits" },
        { key: "referral", label: "Parrainage" },
        { key: "technical", label: "Problème technique" },
        { key: "human", label: "Parler à un conseiller" }
    ];

    var messagesEl = null;
    var inputEl = null;
    var win = null;
    var sessionHash = null;
    var reference = null;
    var lastId = 0;
    var pollTimer = null;

    function getSessionHash() {
        var h = localStorage.getItem("namara_support_hash");
        if (!h) {
            var arr = new Uint8Array(32);
            (window.crypto || window.msCrypto).getRandomValues(arr);
            h = Array.prototype.map.call(arr, function (b) {
                return b.toString(16).padStart(2, "0");
            }).join("");
            localStorage.setItem("namara_support_hash", h);
        }
        return h;
    }

    function el(tag, cls, text) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text) e.textContent = text;
        return e;
    }

    function addBubble(sender, text, time) {
        var b = el("div", "chat-bubble " + sender);
        b.appendChild(document.createTextNode(text));
        if (time) b.appendChild(el("span", "time", time));
        messagesEl.appendChild(b);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function welcome() {
        addBubble("bot", "Bonjour et bienvenue chez NAMARA ! Comment pouvons-nous vous aider aujourd'hui ? Choisissez une catégorie ou écrivez directement votre question.");
    }

    function ensureConversation(callback) {
        fetch(BASE + "/conversation", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_hash: sessionHash })
        }).then(function (r) { return r.json(); }).then(function (data) {
            if (data.reference) {
                reference = data.reference;
                if (callback) callback();
            }
        });
    }

    function pollMessages() {
        if (!reference) return;
        fetch(BASE + "/messages?session_hash=" + encodeURIComponent(sessionHash) + "&after_id=" + lastId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                (data.messages || []).forEach(function (m) {
                    var sender = (m.sender_type === "visitor" || m.sender_type === "user") ? "visitor" : "bot";
                    addBubble(sender, m.text, m.created_at);
                    lastId = Math.max(lastId, m.id);
                });
            });
    }

    function sendText(text) {
        if (!reference) {
            ensureConversation(function () { sendText(text); });
            return;
        }
        addBubble("visitor", text);
        fetch(BASE + "/message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_hash: sessionHash, text: text })
        }).then(function (r) { return r.json(); }).then(function (data) {
            if (data.reply) addBubble("bot", data.reply);
        });
    }

    function chooseCategory(key, label) {
        if (!reference) {
            ensureConversation(function () { chooseCategory(key, label); });
            return;
        }
        if (key === "human") {
            sendText("Je souhaite parler à un conseiller.");
        } else {
            addBubble("visitor", "[Catégorie : " + label + "]");
        }
    }

    function submit() {
        var t = inputEl.value.trim();
        if (t) {
            sendText(t);
            inputEl.value = "";
        }
    }


    function startPolling() {
        if (pollTimer) clearInterval(pollTimer);
        pollMessages();
        pollTimer = setInterval(pollMessages, 5000);
    }

    function buildWidget() {
        var btn = el("button", "chat-widget-btn", "💬 Assistance");
        win = el("div", "chat-window");

        var header = el("div", "chat-header");
        header.appendChild(document.createTextNode("Service client NAMARA"));
        var closeBtn = el("button", "close", "×");
        header.appendChild(closeBtn);

        messagesEl = el("div", "chat-messages");

        var catsEl = el("div", "chat-categories");
        CATEGORIES.forEach(function (c) {
            var b = el("button", "", c.label);
            b.addEventListener("click", function () { chooseCategory(c.key, c.label); });
            catsEl.appendChild(b);
        });

        inputEl = el("input", "");
        inputEl.setAttribute("type", "text");
        inputEl.setAttribute("placeholder", "Écrivez votre message…");
        var sendBtn = el("button", "", "Envoyer");
        var inputRow = el("div", "chat-input");
        inputRow.appendChild(inputEl);
        inputRow.appendChild(sendBtn);

        win.appendChild(header);
        win.appendChild(messagesEl);
        win.appendChild(catsEl);
        win.appendChild(inputRow);

        document.body.appendChild(btn);
        document.body.appendChild(win);

        btn.addEventListener("click", function () {
            var opened = win.classList.toggle("open");
            if (opened) {
                ensureConversation(function () {
                    if (lastId === 0) welcome();
                    startPolling();
                });
            } else if (pollTimer) {
                clearInterval(pollTimer);
            }
        });
        closeBtn.addEventListener("click", function () {
            win.classList.remove("open");
            if (pollTimer) clearInterval(pollTimer);
        });
        sendBtn.addEventListener("click", submit);
        inputEl.addEventListener("keydown", function (e) {
            if (e.key === "Enter") submit();
        });
    }

    sessionHash = getSessionHash();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", buildWidget);
    } else {
        buildWidget();
    }
})();
