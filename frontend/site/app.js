// SamePage site: scroll position drives the story, the scenario strip, and the closing line.
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var narrow = window.matchMedia("(max-width: 56rem)");
  var story = document.getElementById("story");
  var stage = story.querySelector(".stage");
  var railButtons = story.querySelectorAll(".rail button");
  var cases = document.getElementById("cases");
  var track = cases.querySelector(".track");
  var drifters = document.querySelectorAll("[data-drift]");
  var fill = document.querySelector(".fill");
  var STAGES = 4;
  var ticking = false;

  function clamp(value) {
    return Math.max(0, Math.min(1, value));
  }

  // How far a tall section has been scrolled through while its pinned child is on screen.
  function progress(section) {
    var rect = section.getBoundingClientRect();
    var distance = rect.height - window.innerHeight;
    return distance > 0 ? clamp(-rect.top / distance) : 0;
  }

  // Split the closing line into words so each can light up in turn.
  var words = fill.textContent.trim().split(/\s+/);
  fill.setAttribute("aria-label", fill.textContent.trim());
  fill.textContent = "";
  words.forEach(function (word) {
    var span = document.createElement("span");
    span.setAttribute("aria-hidden", "true");
    span.textContent = word + " ";
    fill.appendChild(span);
  });
  var wordSpans = fill.querySelectorAll("span");

  function update() {
    ticking = false;

    var p = progress(story);
    var current = Math.min(STAGES - 1, Math.floor(p * STAGES));
    stage.dataset.stage = String(current);
    stage.style.setProperty("--p", p.toFixed(4));
    railButtons.forEach(function (button, index) {
      button.setAttribute("aria-current", index === current ? "step" : "false");
      button.classList.toggle("done", index < current);
    });

    var still = reduced.matches;
    drifters.forEach(function (row) {
      var shift = still ? 0 : window.scrollY * 0.35 * Number(row.dataset.drift);
      row.style.transform = "translate3d(" + shift + "px, 0, 0)";
    });

    if (still || narrow.matches) {
      track.style.transform = "";
    } else {
      var overflow = track.scrollWidth - track.parentElement.clientWidth;
      track.style.transform = "translate3d(" + (-progress(cases) * Math.max(0, overflow)) + "px, 0, 0)";
    }

    var rect = fill.getBoundingClientRect();
    var lit = clamp((window.innerHeight * 0.85 - rect.top) / (window.innerHeight * 0.55));
    wordSpans.forEach(function (span, index) {
      span.classList.toggle("lit", still || index < Math.round(lit * wordSpans.length));
    });
  }

  function requestUpdate() {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(update);
    }
  }

  railButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      var distance = story.offsetHeight - window.innerHeight;
      var target = story.offsetTop + distance * ((Number(button.dataset.go) + 0.5) / STAGES);
      window.scrollTo({ top: target, behavior: reduced.matches ? "auto" : "smooth" });
    });
  });

  window.addEventListener("scroll", requestUpdate, { passive: true });
  window.addEventListener("resize", requestUpdate);
  reduced.addEventListener("change", requestUpdate);
  narrow.addEventListener("change", requestUpdate);
  document.documentElement.classList.add("ready");
  update();
})();
