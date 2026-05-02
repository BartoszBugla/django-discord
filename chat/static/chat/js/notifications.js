(function () {
    var ctx = window.__chatContext || {};
    var originalTitle = document.title;
    var unreadBump = 0;

    function getCtx() {
        return window.__chatContext || ctx;
    }

    function isPageFocused() {
        return !document.hidden && document.hasFocus();
    }

    function isOwnMessage(data) {
        var c = getCtx();
        return !!(data.from_username && data.from_username === c.username);
    }

    function isViewingChannel(channelId) {
        var c = getCtx();
        return (
            c.channelId != null && Number(c.channelId) === Number(channelId)
        );
    }

    function isViewingDmFrom(fromUserId) {
        var c = getCtx();
        return (
            c.dmUserId != null && Number(c.dmUserId) === Number(fromUserId)
        );
    }

    /** Czy użytkownik ma zobaczyć alert (inna rozmowa lub ta sama, ale karta w tle). */
    function shouldNotifyChannel(data) {
        if (isOwnMessage(data)) {
            return false;
        }
        var same = isViewingChannel(data.channel_id);
        if (same && isPageFocused()) {
            return false;
        }
        return true;
    }

    function shouldNotifyDm(data) {
        if (isOwnMessage(data)) {
            return false;
        }
        var same = isViewingDmFrom(data.from_user_id);
        if (same && isPageFocused()) {
            return false;
        }
        return true;
    }

    function truncate(s, n) {
        if (!s) {
            return "";
        }
        s = String(s);
        return s.length > n ? s.slice(0, n - 1) + "\u2026" : s;
    }

    function bumpTitle() {
        unreadBump += 1;
        if (document.hidden) {
            document.title = "(" + unreadBump + ") " + originalTitle;
        }
    }

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            unreadBump = 0;
            document.title = originalTitle;
        }
    });

    var MAX_TOASTS = 4;

    function ensureToastStack() {
        var stack = document.getElementById("in-app-toast-stack");
        if (!stack) {
            stack = document.createElement("div");
            stack.id = "in-app-toast-stack";
            stack.className = "in-app-toast-stack";
            stack.setAttribute("aria-label", "Powiadomienia w aplikacji");
            document.body.appendChild(stack);
        }
        return stack;
    }

    function showInAppToast(title, body, url) {
        var stack = ensureToastStack();
        while (stack.children.length >= MAX_TOASTS) {
            stack.removeChild(stack.firstChild);
        }

        var wrap = document.createElement("div");
        wrap.className = "in-app-toast";
        wrap.setAttribute("role", "status");
        wrap.setAttribute("aria-live", "polite");

        var closeBtn = document.createElement("button");
        closeBtn.type = "button";
        closeBtn.className = "in-app-toast-close";
        closeBtn.setAttribute("aria-label", "Zamknij powiadomienie");
        closeBtn.textContent = "\u00D7";
        closeBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            removeToast(wrap);
        });

        var inner = document.createElement("div");
        inner.className = "in-app-toast-inner";
        inner.setAttribute("role", "button");
        inner.tabIndex = 0;
        inner.setAttribute(
            "aria-label",
            "Otwórz: " + (title || "").replace(/"/g, "")
        );

        var titleEl = document.createElement("div");
        titleEl.className = "in-app-toast-title";
        titleEl.textContent = title || "";

        var bodyEl = document.createElement("div");
        bodyEl.className = "in-app-toast-body";
        bodyEl.textContent = body || "";

        inner.appendChild(titleEl);
        inner.appendChild(bodyEl);

        inner.addEventListener("click", function () {
            if (url) {
                window.location.href = url;
            }
        });
        inner.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                if (url) {
                    window.location.href = url;
                }
            }
        });

        wrap.appendChild(closeBtn);
        wrap.appendChild(inner);
        stack.appendChild(wrap);

        window.setTimeout(function () {
            removeToast(wrap);
        }, 7000);
    }

    function removeToast(wrap) {
        if (!wrap || !wrap.parentNode) {
            return;
        }
        wrap.classList.add("in-app-toast-out");
        window.setTimeout(function () {
            if (wrap.parentNode) {
                wrap.parentNode.removeChild(wrap);
            }
        }, 220);
    }

    function handleInboxPayload(data) {
        if (!data || !data.kind) {
            return;
        }
        if (isOwnMessage(data)) {
            return;
        }

        var url = "";
        var title = "";
        var body = "";

        if (data.kind === "channel") {
            if (!shouldNotifyChannel(data)) {
                return;
            }
            title = "#" + (data.channel_name || "kanał");
            body =
                (data.from_username || "") +
                ": " +
                truncate(data.preview || "", 120);
            url = "/kanal/" + encodeURIComponent(data.channel_id) + "/";
            if (data.message_id != null && data.message_id !== "") {
                url += "#message-" + encodeURIComponent(String(data.message_id));
            }
        } else if (data.kind === "dm") {
            if (!shouldNotifyDm(data)) {
                return;
            }
            title = "Wiadomość od " + (data.from_username || "użytkownik");
            body = truncate(data.preview || "", 120);
            url = "/dm/" + encodeURIComponent(data.from_user_id) + "/";
            if (data.message_id != null && data.message_id !== "") {
                url += "#message-" + encodeURIComponent(String(data.message_id));
            }
        } else {
            return;
        }

        showInAppToast(title, body, url);

        if (document.hidden || !document.hasFocus()) {
            bumpTitle();
        }
    }

    function connectInbox() {
        var protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        var url = protocol + "//" + window.location.host + "/ws/inbox/";
        var socket = new WebSocket(url);

        socket.onmessage = function (e) {
            try {
                var data = JSON.parse(e.data);
                handleInboxPayload(data);
            } catch (err) {
                /* ignore */
            }
        };

        socket.onclose = function () {
            window.setTimeout(connectInbox, 4000);
        };

        socket.onerror = function () {
            try {
                socket.close();
            } catch (err) {
                /* ignore */
            }
        };
    }

    connectInbox();

    /** Podgląd stylu toastów (strona ustawień / debug). */
    window.__showAppNotificationDemo = function () {
        showInAppToast(
            "Django Discord — test",
            "Tak wyglądają powiadomienia w aplikacji (WebSocket /ws/inbox/, bez powiadomień systemowych przeglądarki).",
            window.location.pathname || "/"
        );
    };
})();
