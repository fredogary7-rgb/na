(function () {
    "use strict";
    var BASE = "/support/api";

    var messagesEl = document.getElementById("chat-messages");
    var quickEl = document.getElementById("chat-quick");
    var inputEl = document.getElementById("chat-input");
    var sendBtn = document.getElementById("chat-send");

    var sessionHash = null;
    var reference = null;
    var lastId = 0;
    var renderedIds = {};
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

    function addBubble(sender, text, time) {
        var isUser = (sender === "visitor" || sender === "user");
        var row = document.createElement("div");
        row.className = "chat-row " + (isUser ? "user" : "bot");
        if (!isUser) {
            var av = document.createElement("img");
            av.className = "chat-row-avatar";
            av.src = "/static/images/namara.jpeg";
            av.alt = "";
            row.appendChild(av);
        }
        var b = document.createElement("div");
        b.className = "chat-bubble " + (isUser ? "visitor" : "bot");
        b.textContent = text;
        if (time) {
            var t = document.createElement("span");
            t.className = "time";
            t.textContent = time;
            b.appendChild(t);
        }
        row.appendChild(b);
        messagesEl.appendChild(row);
        messagesEl.scrollTop = messagesEl.scrollHeight;
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
        }).catch(function () {});
    }

    function pollMessages() {
        if (!reference) return;
        fetch(BASE + "/messages?session_hash=" + encodeURIComponent(sessionHash) + "&after_id=" + lastId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                (data.messages || []).forEach(function (m) {
                    if (renderedIds[m.id]) return;
                    renderedIds[m.id] = true;
                    var sender = (m.sender_type === "visitor" || m.sender_type === "user") ? "visitor" : "bot";
                    addBubble(sender, m.text, m.created_at);
                    lastId = Math.max(lastId, m.id);
                });
            }).catch(function () {});
    }

    function renderButtons(keys) {
        quickEl.innerHTML = "";
        if (!keys || !keys.length) return;
        keys.forEach(function (k) {
            var b = document.createElement("button");
            b.type = "button";
            b.setAttribute("data-action", k.key);
            b.textContent = k.label;
            quickEl.appendChild(b);
        });
    }

    function sendAction(key, label) {
        if (!reference) {
            ensureConversation(function () { sendAction(key, label); });
            return;
        }
        renderButtons([]);
        fetch(BASE + "/message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_hash: sessionHash, action: key })
        }).then(function (r) { return r.json(); }).then(function (data) {
            renderButtons(data.buttons || []);
            pollMessages();
        }).catch(function () {});
    }

    function sendText(text) {
        if (!reference) {
            ensureConversation(function () { sendText(text); });
            return;
        }
        renderButtons([]);
        fetch(BASE + "/message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_hash: sessionHash, text: text })
        }).then(function (r) { return r.json(); }).then(function (data) {
            renderButtons(data.buttons || []);
            pollMessages();
        }).catch(function () {});
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
        pollTimer = setInterval(pollMessages, 5000);
    }

    function init() {
        sessionHash = getSessionHash();

        sendBtn.addEventListener("click", submit);
        inputEl.addEventListener("keydown", function (e) {
            if (e.key === "Enter") submit();
        });

        // Délégation : gère aussi les boutons rendus côté serveur.
        quickEl.addEventListener("click", function (e) {
            var btn = e.target.closest("button[data-action]");
            if (!btn) return;
            sendAction(btn.getAttribute("data-action"), btn.textContent.trim());
        });

        ensureConversation(function () {
            pollMessages();
            startPolling();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
