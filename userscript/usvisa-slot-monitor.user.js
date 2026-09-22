// ==UserScript==
// @name         US Visa Slot Monitor (Kolkata + Mumbai)
// @namespace    https://github.com/Aaditya17032002/slot-booking
// @version      1.1.0
// @description  Polls USVisaScheduling in a real browser session; Telegram on new/empty checks. Firefox + Tampermonkey/Violentmonkey.
// @author       local
// @match        https://www.usvisascheduling.com/*
// @match        https://*.usvisascheduling.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM.xmlHttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addStyle
// @connect      api.telegram.org
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  // ========== CONFIG (edit these in Tampermonkey) ==========
  const CONFIG = {
    TELEGRAM_BOT_TOKEN: "PASTE_BOT_TOKEN_HERE",
    TELEGRAM_CHAT_ID: "PASTE_CHAT_ID_HERE",
    CONSULATES: ["Kolkata", "Mumbai"], // matched against option text (e.g. KOLKATA VAC)
    VISA_LABEL: "B1/B2",
    // Random delay between full cycles (ms)
    POLL_MIN_MS: 3 * 60 * 1000,
    POLL_MAX_MS: 7 * 60 * 1000,
    // Telegram after every cycle (including no slots)
    NOTIFY_EVERY_CHECK: true,
    // Also alert when Cloudflare / login appears
    ALERT_ON_SESSION_ISSUES: true,
    // Don't spam the same "no slots" more often than this (ms); new slots always alert
    MIN_EMPTY_NOTIFY_GAP_MS: 10 * 60 * 1000,
  };
  // ========================================================

  const STORAGE_KEY = "usvisa_slot_state_v1";
  const LAST_EMPTY_KEY = "usvisa_last_empty_notify_v1";

  function addStyle(css) {
    try {
      if (typeof GM_addStyle === "function") {
        GM_addStyle(css);
        return;
      }
    } catch (_) {}
    const s = document.createElement("style");
    s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  }

  const gmGet = (k, d) => {
    try {
      if (typeof GM_getValue === "function") return GM_getValue(k, d);
    } catch (_) {}
    try {
      const v = localStorage.getItem(k);
      return v == null ? d : JSON.parse(v);
    } catch (_) {
      return d;
    }
  };
  const gmSet = (k, v) => {
    try {
      if (typeof GM_setValue === "function") {
        GM_setValue(k, v);
        return;
      }
    } catch (_) {}
    try {
      localStorage.setItem(k, JSON.stringify(v));
    } catch (_) {}
  };

  function xhr(opts) {
    const fn =
      typeof GM_xmlhttpRequest === "function"
        ? GM_xmlhttpRequest
        : typeof GM !== "undefined" && GM.xmlHttpRequest
          ? GM.xmlHttpRequest
          : null;
    if (!fn) {
      console.error("[USVisa] GM_xmlhttpRequest missing — enable @grant in the script");
      return;
    }
    fn(opts);
  }

  function telegram(text, parseMode) {
    const token = CONFIG.TELEGRAM_BOT_TOKEN;
    const chat = CONFIG.TELEGRAM_CHAT_ID;
    if (!token || token.includes("PASTE_") || !chat || String(chat).includes("PASTE_")) {
      console.warn("[USVisa] Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the script CONFIG");
      setStatus("Set Telegram token/chat in script CONFIG", "warn");
      return;
    }
    const body = {
      chat_id: chat,
      text,
      disable_web_page_preview: true,
    };
    if (parseMode) body.parse_mode = parseMode;

    xhr({
      method: "POST",
      url: `https://api.telegram.org/bot${token}/sendMessage`,
      headers: { "Content-Type": "application/json" },
      data: JSON.stringify(body),
      onload(res) {
        if (res.status >= 200 && res.status < 300) {
          console.log("[USVisa] Telegram OK");
        } else {
          console.error("[USVisa] Telegram error", res.status, res.responseText);
        }
      },
      onerror(err) {
        console.error("[USVisa] Telegram network error", err);
      },
    });
  }

  function nowIst() {
    try {
      return new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
    } catch (_) {
      return new Date().toLocaleString();
    }
  }

  function randPoll() {
    const a = CONFIG.POLL_MIN_MS;
    const b = CONFIG.POLL_MAX_MS;
    return Math.floor(a + Math.random() * (b - a));
  }

  function setStatus(msg, kind) {
    const el = document.getElementById("usvisa-monitor-status");
    if (!el) return;
    el.textContent = msg;
    el.dataset.kind = kind || "info";
  }

  function ensurePanel() {
    if (document.getElementById("usvisa-monitor-panel")) return;
    addStyle(`
      #usvisa-monitor-panel {
        position: fixed; z-index: 2147483646; right: 12px; bottom: 12px;
        max-width: 280px; padding: 10px 12px; border-radius: 10px;
        background: rgba(15, 23, 42, 0.92); color: #e2e8f0;
        font: 12px/1.4 system-ui, sans-serif; box-shadow: 0 8px 24px rgba(0,0,0,.35);
      }
      #usvisa-monitor-panel strong { display:block; margin-bottom: 4px; color: #93c5fd; }
      #usvisa-monitor-status[data-kind="warn"] { color: #fbbf24; }
      #usvisa-monitor-status[data-kind="ok"] { color: #86efac; }
      #usvisa-monitor-status[data-kind="alert"] { color: #fca5a5; }
      #usvisa-monitor-panel button {
        margin-top: 8px; margin-right: 6px; padding: 4px 8px; border: 0; border-radius: 6px;
        background: #334155; color: #f8fafc; font-size: 11px; cursor: pointer;
      }
    `);
    const panel = document.createElement("div");
    panel.id = "usvisa-monitor-panel";
    panel.innerHTML = `
      <strong>US Visa monitor</strong>
      <div id="usvisa-monitor-status">Starting…</div>
      <button type="button" id="usvisa-check-now">Check now</button>
      <button type="button" id="usvisa-test-tg">Test Telegram</button>
    `;
    document.documentElement.appendChild(panel);
    document.getElementById("usvisa-check-now").addEventListener("click", () => {
      runCycle(true);
    });
    document.getElementById("usvisa-test-tg").addEventListener("click", () => {
      telegram(
        `<b>ℹ️ US Visa Monitor</b>\n━━━━━━━━━━━━━━━━━━━━\n\nFirefox userscript Telegram test OK.\n\n<i>${escapeHtml(nowIst())}</i>`,
        "HTML"
      );
      setStatus("Telegram test sent", "ok");
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function pageKind() {
    const t = (document.title || "").toLowerCase();
    const body = (document.body && document.body.innerText) || "";
    const low = body.toLowerCase();
    if (
      t.includes("just a moment") ||
      low.includes("performing security verification") ||
      low.includes("verify you are human")
    ) {
      return "cloudflare";
    }
    if (low.includes("we're sorry, but something went wrong") || low.includes("error id #")) {
      return "blocked";
    }
    if (
      document.querySelector('input[type="password"]') ||
      t.includes("sign in") ||
      t.includes("userdetails") ||
      low.includes("self asserted")
    ) {
      return "login";
    }
    if (low.includes("security question")) return "security";
    return "app";
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function findPostSelect() {
    const selects = Array.from(document.querySelectorAll("select"));
    for (const sel of selects) {
      const opts = Array.from(sel.options).map((o) => o.textContent || "");
      const joined = opts.join(" ").toLowerCase();
      if (
        joined.includes("kolkata") ||
        joined.includes("mumbai") ||
        joined.includes("vac") ||
        joined.includes("consular")
      ) {
        return sel;
      }
    }
    return selects[0] || null;
  }

  function optionForCity(select, city) {
    const needle = city.toLowerCase();
    const aliases = needle === "kolkata" ? ["kolkata", "calcutta"] : needle === "mumbai" ? ["mumbai", "bombay"] : [needle];
    return Array.from(select.options).find((o) => {
      const t = (o.textContent || "").toLowerCase();
      return aliases.some((a) => t.includes(a));
    });
  }

  async function selectCity(select, city) {
    const opt = optionForCity(select, city);
    if (!opt) return false;
    select.value = opt.value;
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(2500 + Math.random() * 1500);
    return true;
  }

  function parseSlotsForCity(city) {
    const text = (document.body && document.body.innerText) || "";
    const low = text.toLowerCase();
    const noAvail =
      low.includes("no appointments available") ||
      low.includes("there are no available appointments") ||
      low.includes("no appointment slots") ||
      low.includes("currently no availability");

    const slots = [];
    const dateRe =
      /\b(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+20\d{2}|\d{4}-\d{2}-\d{2})\b/gi;
    let m;
    while ((m = dateRe.exec(text)) !== null) {
      slots.push({ consulate: city, date: m[1], time: "" });
      if (slots.length >= 30) break;
    }

    // Available-looking calendar cells
    document.querySelectorAll("[class*='available'], [data-available='true'], td a, button").forEach((el) => {
      const label = (el.getAttribute("aria-label") || el.textContent || "").trim();
      if (!label || label.length > 80) return;
      const dm = label.match(dateRe);
      if (dm) slots.push({ consulate: city, date: dm[0], time: "" });
    });

    if (noAvail && slots.length === 0) return [];
    // Dedupe
    const seen = new Set();
    return slots.filter((s) => {
      const k = `${s.consulate}|${s.date}|${s.time}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }

  function slotKey(s) {
    return `${s.consulate}|${s.date}|${s.time}`;
  }

  function diffNew(current) {
    const prev = gmGet(STORAGE_KEY, { slots: [] });
    const known = new Set((prev.slots || []).map(slotKey));
    return current.filter((s) => !known.has(slotKey(s)));
  }

  function saveState(slots) {
    gmSet(STORAGE_KEY, { updated_at: new Date().toISOString(), slots });
  }

  function formatTelegram(slots, newSlots) {
    const cities = CONFIG.CONSULATES.join(", ");
    if (newSlots.length) {
      let msg = `<b>🚨 NEW SLOT AVAILABLE</b>\n━━━━━━━━━━━━━━━━━━━━\n\n<b>Visa</b>  ·  ${escapeHtml(CONFIG.VISA_LABEL)}\n\n<b>New openings</b>\n`;
      for (const s of newSlots) {
        msg += `\n📍 <b>${escapeHtml(s.consulate)}</b>\n    •  ${escapeHtml(s.date)}${s.time ? "  ·  " + escapeHtml(s.time) : ""}\n`;
      }
      msg += `\n🔗 Open the tab in Firefox and book manually.\n\n<i>${escapeHtml(nowIst())}</i>`;
      return msg;
    }
    if (slots.length) {
      let msg = `<b>📋 Check complete</b>\n━━━━━━━━━━━━━━━━━━━━\n\n<b>Status</b>  ·  Slots visible (no new ones)\n<b>Watching</b>  ·  ${escapeHtml(cities)}\n`;
      for (const s of slots) {
        msg += `\n• ${escapeHtml(s.consulate)} — ${escapeHtml(s.date)}`;
      }
      msg += `\n\n<i>${escapeHtml(nowIst())}</i>`;
      return msg;
    }
    return (
      `<b>📭 Check complete</b>\n━━━━━━━━━━━━━━━━━━━━\n\n` +
      `<b>Status</b>  ·  No appointments available\n` +
      `<b>Checked</b>  ·  ${escapeHtml(cities)}\n\n` +
      `I'll keep watching in this Firefox tab.\n\n` +
      `<i>${escapeHtml(nowIst())}</i>`
    );
  }

  let cycleLock = false;
  let nextTimer = null;

  async function runCycle(manual) {
    if (cycleLock) return;
    cycleLock = true;
    try {
      ensurePanel();
      const kind = pageKind();
      if (kind === "cloudflare" || kind === "blocked" || kind === "login" || kind === "security") {
        setStatus(`Needs you: ${kind}`, "warn");
        if (CONFIG.ALERT_ON_SESSION_ISSUES) {
          telegram(
            `<b>⚠️ Monitor needs attention</b>\n━━━━━━━━━━━━━━━━━━━━\n\n` +
              `<b>Issue</b>\n${escapeHtml(kind)}\n\n` +
              `Open Firefox and complete Cloudflare / login.\nKeep this tab open.\n\n` +
              `<i>${escapeHtml(nowIst())}</i>`,
            "HTML"
          );
        }
        scheduleNext();
        return;
      }

      setStatus("Checking consulates…", "info");
      const select = findPostSelect();
      const all = [];

      if (select) {
        for (const city of CONFIG.CONSULATES) {
          setStatus(`Checking ${city}…`, "info");
          const ok = await selectCity(select, city);
          if (!ok) {
            console.warn("[USVisa] No dropdown option for", city);
            continue;
          }
          all.push(...parseSlotsForCity(city));
        }
      } else {
        // Already on a calendar view — parse once per configured city label if present
        for (const city of CONFIG.CONSULATES) {
          all.push(...parseSlotsForCity(city));
        }
      }

      // Dedupe
      const seen = new Set();
      const slots = all.filter((s) => {
        const k = slotKey(s);
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      });

      const neu = diffNew(slots);
      saveState(slots);

      if (neu.length) {
        setStatus(`NEW slots: ${neu.length}`, "alert");
        telegram(formatTelegram(slots, neu), "HTML");
      } else if (CONFIG.NOTIFY_EVERY_CHECK) {
        const lastEmpty = gmGet(LAST_EMPTY_KEY, 0);
        const now = Date.now();
        if (slots.length || now - lastEmpty > CONFIG.MIN_EMPTY_NOTIFY_GAP_MS || manual) {
          telegram(formatTelegram(slots, []), "HTML");
          if (!slots.length) gmSet(LAST_EMPTY_KEY, now);
        }
        setStatus(
          slots.length ? `Listed ${slots.length} (no new) · next soon` : "No slots · next soon",
          "ok"
        );
      } else {
        setStatus(slots.length ? `${slots.length} listed` : "No slots", "ok");
      }
    } catch (err) {
      console.error("[USVisa] cycle error", err);
      setStatus("Error — see console", "warn");
      telegram(
        `<b>⚠️ Monitor error</b>\n\n${escapeHtml(String(err && err.message ? err.message : err))}\n\n<i>${escapeHtml(nowIst())}</i>`,
        "HTML"
      );
    } finally {
      cycleLock = false;
      scheduleNext();
    }
  }

  function scheduleNext() {
    if (nextTimer) clearTimeout(nextTimer);
    const wait = randPoll();
    const mins = Math.round(wait / 60000);
    setStatus((document.getElementById("usvisa-monitor-status")?.textContent || "") + ` · next ~${mins}m`, "info");
    nextTimer = setTimeout(() => {
      // Soft reload keeps session and re-runs script; avoids stuck SPA state
      location.reload();
    }, wait);
  }

  // Boot
  ensurePanel();
  // First run after short settle (SPA may still hydrate)
  setTimeout(() => runCycle(false), 4000);
})();
