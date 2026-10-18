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
  var PAGE = 10;

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
      await show(term, found.results, 0, mine);
    }

    /* Results arrive as handles; each one's data is fetched only when it is about to be shown, so
     * a search of 800 matches costs ten fetches rather than 800. "Show more" is what fetches the
     * next ten, which is why the count and the list can disagree until it is pressed. */
    async function show(term, handles, from, mine) {
      var data = await Promise.all(handles.slice(from, from + PAGE).map(function (r) {
        return r.data();
      }));
      if (mine !== token) return;
      render(term, handles, from, data, mine);
    }

    function render(term, handles, from, results, mine) {
      var total = handles.length;
      if (from === 0) {
        panel.textContent = "";
        panel.removeAttribute("aria-busy");
        if (!total) {
          panel.appendChild(el("p", "search-note",
            "Nothing matches " + term + " in what is ticked above."));
          return;
        }
        panel.appendChild(el("p", "search-note", total === 1 ? "1 result" : total + " results"));
        panel.appendChild(el("ul", "search-list"));
      }
      var more = panel.querySelector(".search-more");
      if (more) more.remove();
      var list = panel.querySelector(".search-list");
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
      var shown = from + results.length;
      if (shown < total) {
        var button = el("button", "search-more",
          "Show " + Math.min(PAGE, total - shown) + " more of " + total);
        button.type = "button";
        button.addEventListener("click", function () {
          button.disabled = true;
          show(term, handles, shown, mine);
        });
        panel.appendChild(button);
      }
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
