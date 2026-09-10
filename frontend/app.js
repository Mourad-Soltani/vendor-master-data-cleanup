// Author: Mourad.Soltani
(function () {
  "use strict";

  function setOutput(el, obj) {
    // textContent, never innerHTML. User-supplied strings never hit the DOM as markup.
    el.textContent = JSON.stringify(obj, null, 2);
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let data;
    try {
      data = await res.json();
    } catch (_e) {
      data = { error: "non_json_response", status: res.status };
    }
    return data;
  }

  function parseField(el) {
    try {
      return { ok: true, value: JSON.parse(el.value) };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const aEl = document.getElementById("vendor-a");
    const bEl = document.getElementById("vendor-b");
    const listEl = document.getElementById("vendor-list");
    const classifyOut = document.getElementById("classify-out");
    const dedupeOut = document.getElementById("dedupe-out");

    document.getElementById("classify-btn").addEventListener("click", async function () {
      const a = parseField(aEl);
      const b = parseField(bEl);
      if (!a.ok || !b.ok) {
        setOutput(classifyOut, { error: "invalid_json" });
        return;
      }
      const data = await postJson("/api/classify", { a: a.value, b: b.value });
      setOutput(classifyOut, data);
    });

    document.getElementById("dedupe-btn").addEventListener("click", async function () {
      const v = parseField(listEl);
      if (!v.ok) {
        setOutput(dedupeOut, { error: "invalid_json" });
        return;
      }
      const data = await postJson("/api/deduplicate", { vendors: v.value });
      setOutput(dedupeOut, data);
    });
  });
})();
