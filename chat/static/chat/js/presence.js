(function () {
  var PING_MS = 10000;
  var HEARTBEAT_MS = 30000;

  function connect() {
    var protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    var url = protocol + "//" + window.location.host + "/ws/presence/";
    var socket = new WebSocket(url);
    var pingTimer = null;

    function sendPing() {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "ping" }));
      }
    }

    socket.onopen = function () {
      window.__presenceLastPongAt = Date.now();
      sendPing();
      if (pingTimer) {
        clearInterval(pingTimer);
      }
      pingTimer = setInterval(sendPing, PING_MS);
    };

    socket.onmessage = function (e) {
      try {
        var data = JSON.parse(e.data);
        if (data.type === "pong") {
          window.__presenceLastPongAt = Date.now();
        }
      } catch (err) {
        /* ignore */
      }
    };

    socket.onclose = function () {
      if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
      window.setTimeout(connect, 3000);
    };

    socket.onerror = function () {
      try {
        socket.close();
      } catch (e) {
        /* ignore */
      }
    };
  }

  connect();

  function applyPresenceUi(online) {
    var root = document.getElementById("profile-status-indicator");
    if (!root) {
      return;
    }
    var dot = root.querySelector(".status-dot");
    var label = root.querySelector(".status-label");
    if (dot) {
      dot.classList.toggle("online", online);
      dot.classList.toggle("offline", !online);
    }
    if (label) {
      label.textContent = online ? "Online" : "Offline";
    }
  }

  function pollOthersProfilePresence() {
    var root = document.getElementById("profile-status-indicator");
    if (!root || !root.dataset.presencePollUrl) {
      return;
    }
    if (root.dataset.viewerIsSubject === "1") {
      return;
    }
    var url = root.dataset.presencePollUrl;

    function sync() {
      fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          applyPresenceUi(!!data.appears_online);
        })
        .catch(function () {
          /* keep previous UI */
        });
    }

    sync();
    setInterval(sync, PING_MS);
  }

  function tickOwnProfileFromPongs() {
    var root = document.getElementById("profile-status-indicator");
    if (!root || root.dataset.viewerIsSubject !== "1") {
      return;
    }
    var last = window.__presenceLastPongAt || 0;
    var online = last > 0 && Date.now() - last < HEARTBEAT_MS;
    applyPresenceUi(online);
  }

  pollOthersProfilePresence();
  setInterval(tickOwnProfileFromPongs, 5000);
})();
