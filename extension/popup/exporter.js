"use strict";

import {
  EXPORT_FILENAME,
  buildExport,
  cookieValue,
  isOnlyFansUrl
} from "../lib/export-data.js";

const button = document.querySelector("#export");
const status = document.querySelector("#status");

function showStatus(message, kind = "") {
  status.textContent = message;
  status.className = kind;
}

async function activeOnlyFansTab() {
  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  const tab = tabs[0];
  if (!tab || typeof tab.id !== "number" || !isOnlyFansUrl(tab.url || "")) {
    throw new Error("Abre OnlyFans en esta pestaña antes de exportar.");
  }
  return tab;
}

async function collectAuth() {
  const tab = await activeOnlyFansTab();
  const cookieOptions = { domain: "onlyfans.com" };
  if (tab.cookieStoreId) {
    cookieOptions.storeId = tab.cookieStoreId;
  }

  let session;
  try {
    session = await browser.tabs.sendMessage(tab.id, {
      type: "ofbackup-read-session"
    });
  } catch (_error) {
    throw new Error("Recarga la pestaña de OnlyFans y vuelve a intentarlo.");
  }
  const cookies = await browser.cookies.getAll(cookieOptions);

  const auth = {
    sess: cookieValue(cookies, "sess"),
    auth_id: cookieValue(cookies, "auth_id"),
    "x-bc": session && session.xBc ? session.xBc : "",
    user_agent: session && session.userAgent ? session.userAgent : ""
  };

  if (!auth.sess || !auth.auth_id) {
    throw new Error("No encontré una sesión activa. Inicia sesión y vuelve a intentarlo.");
  }
  if (!auth["x-bc"]) {
    throw new Error("Falta x-bc. Recarga OnlyFans, espera a que termine y prueba otra vez.");
  }
  if (!auth.user_agent) {
    throw new Error("No se pudo leer el User-Agent del navegador.");
  }
  return auth;
}

async function downloadExport(auth) {
  const payload = buildExport(auth);
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], {
    type: "application/json"
  });
  const url = URL.createObjectURL(blob);
  try {
    await browser.downloads.download({
      url,
      filename: EXPORT_FILENAME,
      conflictAction: "overwrite",
      saveAs: false
    });
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

button.addEventListener("click", async () => {
  button.disabled = true;
  showStatus("Leyendo la sesión local…");
  try {
    const auth = await collectAuth();
    await downloadExport(auth);
    showStatus("✓ OFBackup-auth.json guardado en Descargas.", "success");
  } catch (error) {
    showStatus(`✗ ${error.message || "No se pudo exportar."}`, "error");
  } finally {
    button.disabled = false;
  }
});
