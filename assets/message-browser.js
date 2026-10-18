/* The message browser: a tree of one Information Package, loaded from tree.json.
 *
 * The Declaration package has 9,064 positions, so rows are built only when a node is opened and
 * the whole tree is never in the DOM at once. Names, definitions and code list names arrive in a
 * string table and are referenced by index, because the same 243 classes fill those positions.
 *
 * It needs no framework. If it fails to load, the page still carries the top-level table and the
 * schema itself, which is the point of not making the browser the only route to the content. */
(function () {
  "use strict";

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function Browser(root) {
    this.root = root;
    this.url = root.getAttribute("data-tree");
    this.treeEl = root.querySelector(".browser-tree");
    this.detailEl = root.querySelector(".browser-detail");
    this.filterEl = root.querySelector(".browser-filter");
    this.countEl = root.querySelector(".browser-count");
    this.rows = {};      // path -> row element
    this.kids = {};      // path -> children container
    this.nodes = {};     // path -> node
    this.selected = null;
    this.load();
  }

  Browser.prototype.load = function () {
    var self = this;
    fetch(this.url).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (data) {
      self.data = data;
      self.s = data.strings;
      self.index(data.root, null);
      self.renderCounts();
      self.draw();
      self.bind();
      var hash = decodeURIComponent(location.hash.replace(/^#/, ""));
      if (hash && self.nodes[hash]) self.reveal(hash);
    }).catch(function () {
      self.root.classList.add("browser-failed");
      self.treeEl.textContent = "The structure browser could not load its data. "
        + "The schema and the top-level table below carry the same content.";
    });
  };

  Browser.prototype.index = function (node, parentPath) {
    var path = parentPath ? parentPath + "/" + node.s : node.s;
    node._p = path;
    node._parent = parentPath;
    this.nodes[path] = node;
    var self = this;
    (node.k || []).forEach(function (k) { self.index(k, path); });
  };

  Browser.prototype.str = function (i) {
    return (i == null || i < 0) ? "" : this.s[i];
  };

  Browser.prototype.renderCounts = function () {
    var st = this.data.stats;
    this.countEl.textContent = st.nodes.toLocaleString() + " positions · "
      + st.classes.toLocaleString() + " classes · "
      + st.elements.toLocaleString() + " elements · " + st.maxDepth + " levels deep";
  };

  /* Build the row for one node. Children are not built until it opens. */
  Browser.prototype.row = function (node, depth) {
    var wrap = el("div", "node");
    var row = el("div", "row");
    row.tabIndex = 0;
    row.setAttribute("role", "treeitem");
    var hasKids = !!(node.k && node.k.length);
    var twisty = el("span", "twisty", hasKids ? "▸" : "");
    row.appendChild(twisty);
    row.appendChild(el("span", "nm" + (node.t === "C" ? " cls" : ""), this.str(node.n)));
    if (node.g) row.appendChild(el("code", "tag", node.g));
    row.appendChild(el("span", "card", node.c));
    if (hasKids) {
      row.appendChild(el("span", "kidcount",
        (node.nc ? node.nc + "C" : "") + (node.nc && node.nd ? " " : "") + (node.nd ? node.nd + "E" : "")));
    }
    wrap.appendChild(row);
    var kids = el("div", "kids");
    kids.hidden = true;
    wrap.appendChild(kids);
    this.rows[node._p] = row;
    this.kids[node._p] = kids;
    row.dataset.path = node._p;
    row.setAttribute("aria-expanded", hasKids ? "false" : "");
    var self = this;
    function toggle(e) {
      if (e) e.stopPropagation();
      if (!hasKids) return;
      if (kids.hidden) self.open(node, depth);
      else { kids.hidden = true; twisty.textContent = "▸"; row.setAttribute("aria-expanded", "false"); }
    }
    twisty.addEventListener("click", toggle);
    row.addEventListener("click", function () { self.select(node); if (kids.hidden) toggle(); });
    row.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); self.select(node); toggle(); }
      if (e.key === "ArrowRight" && kids.hidden) toggle();
      if (e.key === "ArrowLeft" && !kids.hidden) toggle();
    });
    return wrap;
  };

  Browser.prototype.open = function (node, depth) {
    var kids = this.kids[node._p], row = this.rows[node._p];
    if (!kids.firstChild) {
      var self = this;
      (node.k || []).forEach(function (k) {
        if (self.filtered && !self.filtered[k._p]) return;
        kids.appendChild(self.row(k, depth + 1));
      });
    }
    kids.hidden = false;
    row.querySelector(".twisty").textContent = "▾";
    row.setAttribute("aria-expanded", "true");
  };

  Browser.prototype.draw = function () {
    this.rows = {};
    this.kids = {};
    this.treeEl.textContent = "";
    this.treeEl.appendChild(this.row(this.data.root, 1));
    this.open(this.data.root, 1);
  };

  Browser.prototype.expandTo = function (depth) {
    var self = this;
    (function walk(node, d) {
      if (d >= depth || !node.k) return;
      self.open(node, d);
      node.k.forEach(function (k) {
        if (!self.filtered || self.filtered[k._p]) walk(k, d + 1);
      });
    })(this.data.root, 1);
  };

  Browser.prototype.reveal = function (path) {
    var chain = [], p = path;
    while (p) { chain.unshift(p); p = this.nodes[p] && this.nodes[p]._parent; }
    for (var i = 0; i < chain.length - 1; i++) this.open(this.nodes[chain[i]], i + 1);
    var row = this.rows[path];
    if (row) {
      this.select(this.nodes[path]);
      row.scrollIntoView({ block: "center" });
    }
  };

  Browser.prototype.select = function (node) {
    if (this.selected) this.selected.classList.remove("on");
    var row = this.rows[node._p];
    if (row) { row.classList.add("on"); this.selected = row; }
    this.detail(node);
    if (history.replaceState) history.replaceState(null, "", "#" + encodeURIComponent(node._p));
  };

  Browser.prototype.detail = function (node) {
    var d = this.detailEl;
    d.textContent = "";
    d.appendChild(el("h3", null, this.str(node.n)));
    d.appendChild(el("p", "bpath", node._p));
    var def = this.str(node.d);
    if (def) d.appendChild(el("p", "bdef", def));
    var rem = this.str(node.r);
    if (rem) d.appendChild(el("p", "brem", "Remark: " + rem));
    var t = el("table", "facts");
    function add(label, value, href) {
      if (!value) return;
      var tr = el("tr");
      tr.appendChild(el("th", null, label));
      var td = el("td");
      if (href) {
        var a = el("a", null, value);
        a.href = href;
        td.appendChild(a);
      } else td.textContent = value;
      tr.appendChild(td);
      t.appendChild(tr);
    }
    add("Kind", node.t === "C" ? "Class" : "Element");
    add("Occurs", node.c);
    add("Format", node.f);
    add("JSON tag", node.g);
    add("XML tag", node.x);
    add("Code list", this.str(node.ln), node.l || null);
    add("Vocabulary term", node.v ? node.v.replace(/^https?:\/\/[^/]+\//, "") : "", node.v || null);
    add("WCO ID", node.w);
    add("Position ID", node.u);
    add("Sequence", node.q);
    add("Source", node.src);
    if (node.k && node.k.length) {
      add("Contains", (node.nc || 0) + " classes, " + (node.nd || 0) + " elements");
    }
    if (node.ub && node.ub.length) add("Used by", node.ub.join(", "));
    d.appendChild(t);
  };

  /* Filtering keeps a node if it matches, together with its ancestors, so a match is always shown
   * in the structure it sits in rather than as a bare list. */
  Browser.prototype.filter = function (q) {
    q = q.trim().toLowerCase();
    if (!q) {
      this.filtered = null;
      this.draw();
      this.expandTo(2);
      this.renderCounts();
      return;
    }
    var keep = {}, hits = 0, self = this;
    Object.keys(this.nodes).forEach(function (p) {
      var n = self.nodes[p];
      var hay = (self.str(n.n) + " " + (n.g || "") + " " + (n.w || "") + " " + (n.x || "")).toLowerCase();
      if (hay.indexOf(q) === -1) return;
      hits++;
      var q2 = p;
      while (q2) { keep[q2] = true; q2 = self.nodes[q2]._parent; }
    });
    this.filtered = keep;
    if (!hits) {
      this.treeEl.textContent = "Nothing in this message matches " + q + ".";
      this.countEl.textContent = "no matches";
      return;
    }
    this.draw();
    this.expandTo(99);
    this.countEl.textContent = hits.toLocaleString() + " matching "
      + (hits === 1 ? "position" : "positions") + " of " + this.data.stats.nodes.toLocaleString();
  };

  Browser.prototype.bind = function () {
    var self = this, timer;
    this.filterEl.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { self.filter(self.filterEl.value); }, 120);
    });
    this.root.querySelectorAll("[data-act]").forEach(function (b) {
      b.addEventListener("click", function () {
        var act = b.getAttribute("data-act");
        if (act === "collapse") { self.draw(); }
        if (act === "two") { self.draw(); self.expandTo(2); }
        if (act === "three") { self.draw(); self.expandTo(3); }
      });
    });
    this.expandTo(2);
  };

  window.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".browser[data-tree]").forEach(function (n) { new Browser(n); });
  });
})();
