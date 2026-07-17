import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  EXPORT_FILENAME,
  buildExport,
  cookieValue,
  isOnlyFansUrl
} from "../extension/lib/export-data.js";

test("accepts only OnlyFans HTTPS page hosts", () => {
  assert.equal(isOnlyFansUrl("https://onlyfans.com/"), true);
  assert.equal(isOnlyFansUrl("https://api.onlyfans.com/test"), true);
  assert.equal(isOnlyFansUrl("http://onlyfans.com/"), false);
  assert.equal(isOnlyFansUrl("https://onlyfans.com.example.org/"), false);
  assert.equal(isOnlyFansUrl("not-a-url"), false);
});

test("finds a cookie by its exact name", () => {
  const cookies = [
    { name: "sess-extra", value: "wrong" },
    { name: "sess", value: "right" }
  ];
  assert.equal(cookieValue(cookies, "sess"), "right");
  assert.equal(cookieValue(cookies, "auth_id"), "");
});

test("builds the versioned import format without extra fields", () => {
  const result = buildExport(
    {
      sess: "session",
      auth_id: "42",
      "x-bc": "xbc",
      user_agent: "Firefox",
      ignored: "discard"
    },
    "2026-07-17T12:00:00.000Z"
  );
  assert.deepEqual(result, {
    format: "ofbackup-auth",
    version: 1,
    created_at: "2026-07-17T12:00:00.000Z",
    auth: {
      sess: "session",
      auth_id: "42",
      "x-bc": "xbc",
      user_agent: "Firefox"
    }
  });
  assert.equal(EXPORT_FILENAME, "OFBackup-auth.json");
});

test("Chrome manifest stays private and limited to OnlyFans", async () => {
  const manifest = JSON.parse(
    await readFile(new URL("../chrome/manifest.json", import.meta.url), "utf8")
  );
  assert.equal(manifest.manifest_version, 3);
  assert.equal(manifest.version, "1.0.0");
  assert.equal("browser_specific_settings" in manifest, false);
  assert.deepEqual(manifest.permissions, ["activeTab", "cookies", "downloads"]);
  assert.deepEqual(manifest.host_permissions, [
    "https://onlyfans.com/*",
    "https://*.onlyfans.com/*"
  ]);

  const sessionScript = await readFile(
    new URL("../chrome/content/session.js", import.meta.url),
    "utf8"
  );
  assert.match(sessionScript, /sendResponse\(/);
  assert.doesNotMatch(sessionScript, /Promise\.resolve/);
});
