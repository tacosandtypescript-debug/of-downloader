"use strict";

browser.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== "ofbackup-read-session") {
    return undefined;
  }

  return Promise.resolve({
    xBc: window.localStorage.getItem("bcTokenSha") || "",
    userAgent: window.navigator.userAgent || ""
  });
});
