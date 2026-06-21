/* SAM-style local UI — vanilla JS, no framework, no CDN. Client-side view router.
   Later tasks (matters/hub/chat/history/settings) extend this with data fetches. */
(function () {
  "use strict";
  var VIEWS = ["chat", "matters", "hub", "history", "settings"];

  // Shared app state (active matter is the D-18 scope for chat + hub).
  var state = { matter: null };
  window.appState = state;

  function showView(name) {
    if (VIEWS.indexOf(name) === -1) return;
    VIEWS.forEach(function (v) {
      var el = document.getElementById("view-" + v);
      if (el) el.classList.toggle("active", v === name);
    });
    document.querySelectorAll(".nav-item").forEach(function (b) {
      b.classList.toggle("active", b.dataset.view === name);
    });
    // Per-view refresh hooks installed by later tasks.
    var hook = (window.viewHooks || {})[name];
    if (typeof hook === "function") hook();
  }
  window.showView = showView;
  window.viewHooks = window.viewHooks || {};

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".nav-item").forEach(function (b) {
      b.addEventListener("click", function () { showView(b.dataset.view); });
    });
    showView("chat");
  });
})();
