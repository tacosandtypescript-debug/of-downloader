export const EXPORT_FORMAT = "ofbackup-auth";
export const EXPORT_VERSION = 1;
export const EXPORT_FILENAME = "OFBackup-auth.json";

export function isOnlyFansUrl(value) {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    return (
      url.protocol === "https:" &&
      (host === "onlyfans.com" || host.endsWith(".onlyfans.com"))
    );
  } catch (_error) {
    return false;
  }
}

export function cookieValue(cookies, name) {
  const cookie = cookies.find((item) => item.name === name);
  return cookie ? cookie.value : "";
}

export function buildExport(auth, createdAt = new Date().toISOString()) {
  return {
    format: EXPORT_FORMAT,
    version: EXPORT_VERSION,
    created_at: createdAt,
    auth: {
      sess: auth.sess,
      auth_id: auth.auth_id,
      "x-bc": auth["x-bc"],
      user_agent: auth.user_agent
    }
  };
}
