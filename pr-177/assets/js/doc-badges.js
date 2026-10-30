/**
 * Adds "class" / "meth" badges to the right-side ToC for API reference pages.
 *
 * mkdocstrings wraps classes in  div.doc-class  and methods in
 * div.doc-class > ... > div.doc-function,  each with a .doc-heading child
 * whose id matches the href used by mkdocs-material's secondary nav.
 *
 * Timing note:
 *   This script is a plain <script> at the end of <body>, so the DOM is
 *   already fully parsed when it runs.  We therefore call applyBadges()
 *   immediately — no DOMContentLoaded or document$ needed for the first run.
 *   document$.subscribe() is still registered to re-apply badges on
 *   instant-navigation hops (navigation.instant), where the DOM is swapped
 *   by mkdocs-material after the initial page load.
 */

function applyBadges() {
  // Class headings — h*.doc-heading is a direct child of div.doc-class
  document.querySelectorAll(".doc-class > .doc-heading[id]").forEach(function (h) {
    addBadge(h.id, "class", "doc-toc-badge--class");
  });

  // Method headings — h*.doc-heading inside div.doc-function inside div.doc-class
  document.querySelectorAll(".doc-class .doc-function > .doc-heading[id]").forEach(function (h) {
    addBadge(h.id, "meth", "doc-toc-badge--meth");
  });
}

function addBadge(id, label, cls) {
  var link = document.querySelector('.md-nav--secondary a[href="#' + id + '"]');
  if (!link || link.querySelector(".doc-toc-badge")) return; // already decorated

  var badge = document.createElement("span");
  badge.className = "doc-toc-badge " + cls;
  badge.textContent = label;

  // The ToC <a> wraps its visible text in <span class="md-ellipsis">.
  // Insert the badge AFTER that span so it is never clipped by text-overflow.
  var ellipsis = link.querySelector(".md-ellipsis");
  if (ellipsis) {
    ellipsis.insertAdjacentElement("afterend", badge);
  } else {
    link.appendChild(badge);
  }
}

// DOM is already ready — run immediately.
applyBadges();

// Also subscribe for instant-navigation re-runs (navigation.instant feature).
if (typeof document$ !== "undefined") {
  document$.subscribe(applyBadges);
}
