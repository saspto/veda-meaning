/* global API_BASE_URL */
const API_BASE = (typeof API_BASE_URL !== "undefined") ? API_BASE_URL : "/api";

const verseRefInput  = document.getElementById("verseRef");
const fetchBtn       = document.getElementById("fetchBtn");
const meaningBtn     = document.getElementById("meaningBtn");
const verseSection   = document.getElementById("verseSection");
const verseTitle     = document.getElementById("verseTitle");
const verseSource    = document.getElementById("verseSource");
const verseText      = document.getElementById("verseText");
const meaningSection = document.getElementById("meaningSection");
const meaningSource  = document.getElementById("meaningSource");
const wordTable      = document.getElementById("wordTable");
const sentenceSection= document.getElementById("sentenceSection");
const spinner        = document.getElementById("spinner");
const errorBox       = document.getElementById("errorBox");

function setRef(r) { verseRefInput.value = r; }

function selectedScript() {
  return document.querySelector('input[name="script"]:checked').value;
}

function showSpinner() {
  spinner.classList.remove("hidden");
  errorBox.classList.add("hidden");
}

function hideSpinner() {
  spinner.classList.add("hidden");
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

async function apiFetch(path, params) {
  const url = new URL(API_BASE + path, window.location.href);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const resp = await fetch(url.toString());
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
  return data;
}

fetchBtn.addEventListener("click", async () => {
  const ref = verseRefInput.value.trim();
  if (!ref) { showError("Please enter a verse reference."); return; }

  showSpinner();
  verseSection.classList.add("hidden");
  meaningSection.classList.add("hidden");

  try {
    const data = await apiFetch("/verse", { ref, script: selectedScript() });
    verseTitle.textContent = ref;
    verseSource.textContent = data.source || "Vedic Scriptures";
    verseText.textContent = data.verse || "(No text returned)";
    verseText.className = "scripture-text" + (selectedScript() === "telugu" ? " telugu" : "");
    verseSection.classList.remove("hidden");
  } catch (e) {
    showError("Could not fetch verse: " + e.message);
  } finally {
    hideSpinner();
  }
});

meaningBtn.addEventListener("click", async () => {
  const ref = verseRefInput.value.trim();
  if (!ref) { showError("Please enter a verse reference."); return; }

  showSpinner();
  meaningSection.classList.add("hidden");

  try {
    const data = await apiFetch("/meaning", { ref, script: selectedScript() });
    renderMeaning(data, selectedScript());
    meaningSection.classList.remove("hidden");
  } catch (e) {
    showError("Could not fetch meaning: " + e.message);
  } finally {
    hideSpinner();
  }
});

function renderMeaning(data, script) {
  const isTelugu = script === "telugu";
  meaningSource.textContent = data.source || "Vedic Sources";

  // Word-by-word table
  const words = data.word_for_word || [];
  if (words.length > 0) {
    const rows = words.map(w => `
      <div class="wg-cell wg-word ${isTelugu ? "telugu" : ""}">${esc(w.word)}</div>
      <div class="wg-cell wg-translit">${esc(w.transliteration || "")}</div>
      <div class="wg-cell wg-meaning">${esc(w.meaning)}</div>
    `).join("");

    wordTable.innerHTML = `
      <p class="word-table-title">Word-by-Word Meaning</p>
      <div class="word-grid">
        <div class="wg-header">Word</div>
        <div class="wg-header">Transliteration</div>
        <div class="wg-header">English Meaning</div>
        ${rows}
      </div>
    `;
  } else {
    wordTable.innerHTML = "<p style='color:var(--text2);font-size:.85rem'>No word-by-word breakdown available.</p>";
  }

  // Sentence-by-sentence
  const sentences = data.sentence || [];
  if (sentences.length > 0) {
    sentenceSection.innerHTML = `<p class="sentence-title">Sentence Meaning</p>` +
      sentences.map(s => {
        const hasOrig = s.text && s.lang !== "en";
        const meaningText = s.meaning || (s.lang === "en" ? s.text : "");
        return `
          <div class="sentence-block">
            ${hasOrig ? `<div class="sentence-original ${isTelugu ? "telugu" : ""}">${esc(s.text)}</div>` : ""}
            ${s.transliteration ? `<div class="sentence-translit">${esc(s.transliteration)}</div>` : ""}
            ${meaningText ? `<div class="sentence-meaning">${esc(meaningText)}</div>` : `<div class="sentence-meaning">${esc(s.text)}</div>`}
          </div>
        `;
      }).join("");
  } else {
    sentenceSection.innerHTML = "";
  }
}

function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

verseRefInput.addEventListener("keydown", e => {
  if (e.key === "Enter") fetchBtn.click();
});
