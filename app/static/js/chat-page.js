(function () {
    "use strict";
    var BASE = "/support/api";

    var messagesEl = document.getElementById("chat-messages");
    var inputEl = document.getElementById("chat-input");
    var sendBtn = document.getElementById("chat-send");

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

    function addBubble(sender, text, time) {
        var b = document.createElement("div");
        b.className = "chat-bubble " + sender;
        b.appendChild(document.createTextNode(text));
        if (time) {
            var t = document.createElement("span");
            t.className = "time";
            t.textContent = time;
            b.appendChild(t);
        }
        messagesEl.appendChild(b);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function welcome() {
        addBubble("bot", "Bonjour et bienvenue chez NAMARA ! Comment pouvons-nous vous aider aujourd'hui ? Écrivez directement votre question.");
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

    function pollMessages(callback) {
        if (!reference) return;
        fetch(BASE + "/messages?session_hash=" + encodeURIComponent(sessionHash) + "&after_id=" + lastId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                (data.messages || []).forEach(function (m) {
                    var sender = (m.sender_type === "visitor" || m.sender_type === "user") ? "visitor" : "bot";
                    addBubble(sender, m.text, m.created_at);
                    lastId = Math.max(lastId, m.id);
                });
                if (callback) callback();
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

        ensureConversation(function () {
            pollMessages(function () {
                if (lastId === 0) welcome();
            });
            startPolling();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
