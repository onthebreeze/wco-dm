/* Search, driven straight off the Pagefind API.
 *
 * Not Pagefind's Default UI. That component cannot start with a filter ticked, and its
 * triggerFilters method - the only way in - turns two values of one filter into an AND, so asking
 * for "classes or properties" asks for pages that are both and returns nothing. The API has a
 * form for OR, {any: [...]}, and using it directly costs about seventy lines and drops a hundred
 * and twenty kilobytes of component from every page.
 *
 * Documentation is always searched. A search that hides the explanation of a thing while showing
 * the thing is worse than one that shows both, so it is appended to whatever the reader ticked and
 * has no checkbox of its own. */
(function () {
  "use strict";

  var DEBOUNCE = 180;
  var LIMIT = 10;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function ready(root) {
    var input = root.querySelector(".search-input");
    var filters = root.querySelector(".search-filters");
    var panel = root.querySelector(".search-results");
    var boxes = [].slice.call(filters.querySelectorAll("input[type=checkbox]"));
    var allVersions = filters.querySelector("#all-versions");
    var pagefind = null;
    var timer = null;
    var token = 0;

    function selected() {
      var show = ["Documentation"];
      boxes.forEach(function (b) {
        if (b !== allVersions && b.checked) show.push(b.value);
      });
      var f = { show: { any: show } };
      if (!allVersions.checked) f.versions = { any: ["current"] };
      return f;
    }

    function open(on) {
      filters.hidden = !on;
      panel.hidden = !on;
    }

    async function load() {
      if (!pagefind) {
        pagefind = await import(root.getAttribute("data-pagefind") + "pagefind.js");
        await pagefind.init();
      }
      return pagefind;
    }

    async function run() {
      var term = input.value.trim();
      if (!term) {
        open(false);
        return;
      }
      open(true);
      var mine = ++token;
      panel.setAttribute("aria-busy", "true");
      var pf;
      try {
        pf = await load();
      } catch (e) {
        panel.textContent = "The search index could not be loaded.";
        return;
      }
      var found = await pf.search(term, { filters: selected() });
      if (mine !== token) return;                       // a later keystroke has overtaken this one
      var data = await Promise.all(found.results.slice(0, LIMIT).map(function (r) {
        return r.data();
      }));
      if (mine !== token) return;
      render(term, found.results.length, data);
    }

    function render(term, total, results) {
      panel.textContent = "";
      panel.removeAttribute("aria-busy");
      if (!total) {
        panel.appendChild(el("p", "search-note",
          "Nothing matches " + term + " in what is ticked above."));
        return;
      }
      var count = el("p", "search-note",
        total === 1 ? "1 result" : total + " results"
          + (total > results.length ? ", showing the first " + results.length : ""));
      panel.appendChild(count);
      var list = el("ul", "search-list");
      results.forEach(function (r) {
        var li = el("li");
        var a = el("a", null, (r.meta && r.meta.title) || r.url);
        a.href = r.url;
        li.appendChild(a);
        var kind = r.meta && r.meta.kind;
        if (kind) {
          var tag = el("span", "pf-kind pf-" + kind.toLowerCase().replace(/[^a-z]+/g, "-"), kind);
          li.appendChild(tag);
        }
        if (r.meta && r.meta.release) {
          li.appendChild(el("span", "pf-kind pf-rel", r.meta.release));
        }
        var ex = el("p", "search-excerpt");
        ex.innerHTML = r.excerpt;                        // Pagefind marks the hit with <mark>
        li.appendChild(ex);
        list.appendChild(li);
      });
      panel.appendChild(list);
    }

    function schedule() {
      clearTimeout(timer);
      timer = setTimeout(run, DEBOUNCE);
    }

    input.addEventListener("input", schedule);
    input.addEventListener("focus", function () { if (input.value.trim()) open(true); });
    boxes.forEach(function (b) { b.addEventListener("change", run); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { input.value = ""; open(false); input.blur(); }
    });
    document.addEventListener("click", function (e) {
      if (!root.contains(e.target)) open(false);
    });
  }

  window.addEventListener("DOMContentLoaded", function () {
    var root = document.querySelector(".search[data-pagefind]");
    if (root) ready(root);
  });
})();
