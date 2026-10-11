(function () {
  "use strict";
  document.documentElement.classList.remove("no-js");
  document.documentElement.classList.add("js");
  document.querySelectorAll("[data-js-only]").forEach(function (el) { el.hidden = false; });

  document.querySelectorAll("form[data-pending-text]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector("button[type=submit]");
      if (!button || button.disabled) { return; }
      button.textContent = form.getAttribute("data-pending-text");
      button.setAttribute("aria-disabled", "true");
      window.setTimeout(function () { button.disabled = true; }, 0);
    });
  });

  var form = document.getElementById("quiz-form");
  if (!form) { return; }

  var questions = Array.prototype.slice.call(form.querySelectorAll(".question"));
  var total = questions.length;
  var palette = document.getElementById("palette");
  var progress = document.getElementById("quiz-progress");
  var counter = document.getElementById("quiz-counter");
  var prev = document.getElementById("prev-btn");
  var next = document.getElementById("next-btn");
  var submit = document.getElementById("submit-btn");
  var timerBox = document.getElementById("timer");
  var timerText = document.getElementById("timer-text");
  var current = 0;
  var submitting = false;

  function isAnswered(i) {
    return !!questions[i].querySelector("input[type=radio]:checked");
  }

  function unansweredCount() {
    var n = 0;
    for (var i = 0; i < total; i++) { if (!isAnswered(i)) { n++; } }
    return n;
  }

  var paletteButtons = questions.map(function (_, i) {
    var li = document.createElement("li");
    var b = document.createElement("button");
    b.type = "button";
    b.textContent = String(i + 1);
    b.setAttribute("aria-label", "Go to question " + (i + 1));
    b.addEventListener("click", function () { show(i); });
    li.appendChild(b);
    palette.appendChild(li);
    return b;
  });

  function refresh() {
    paletteButtons.forEach(function (b, i) {
      b.classList.toggle("is-answered", isAnswered(i));
      if (i === current) { b.setAttribute("aria-current", "true"); } else { b.removeAttribute("aria-current"); }
    });
    var done = total - unansweredCount();
    progress.max = total;
    progress.value = done;
    counter.textContent = done + " of " + total + " answered";
  }

  function show(i) {
    current = Math.max(0, Math.min(total - 1, i));
    questions.forEach(function (q, n) { q.hidden = n !== current; });
    prev.disabled = current === 0;
    next.disabled = current === total - 1;
    submit.classList.toggle("btn-quiet", current !== total - 1);
    refresh();
  }

  form.addEventListener("change", refresh);
  prev.addEventListener("click", function () { show(current - 1); });
  next.addEventListener("click", function () { show(current + 1); });

  form.addEventListener("submit", function (event) {
    if (submitting) { event.preventDefault(); return; }
    var left = unansweredCount();
    var timedOut = form.getAttribute("data-timed-out") === "1";
    if (left > 0 && !timedOut) {
      var ok = window.confirm(
        "You have " + left + " unanswered question" + (left === 1 ? "" : "s") + ". Submit anyway?"
      );
      if (!ok) { event.preventDefault(); return; }
    }
    submitting = true;
    submit.disabled = true;
  });

  var remaining = parseInt(form.getAttribute("data-time-limit"), 10) || 0;
  function paint() {
    var m = Math.floor(remaining / 60), s = remaining % 60;
    timerText.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    timerBox.classList.toggle("is-low", remaining <= 60);
  }
  if (remaining > 0) {
    paint();
    var tick = window.setInterval(function () {
      remaining -= 1;
      paint();
      if (remaining <= 0) {
        window.clearInterval(tick);
        form.setAttribute("data-timed-out", "1");
        form.requestSubmit ? form.requestSubmit() : form.submit();
      }
    }, 1000);
  } else {
    timerBox.hidden = true;
  }

  show(0);
})();