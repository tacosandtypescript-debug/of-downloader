"use strict";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "ofbackup-read-session") {
    return undefined;
  }

  sendResponse({
    xBc: window.localStorage.getItem("bcTokenSha") || "",
    userAgent: window.navigator.userAgent || ""
  });
  return false;
});
