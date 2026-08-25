package com.tacosandtypescript.ofdownloader;

import android.accounts.AccountManager;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;

public final class MainActivity extends Activity {
    private static final int CREATE_EXPORT_FILE = 1001;
    private static final int CHOOSE_GOOGLE_ACCOUNT = 1002;
    private static final String LOGIN_URL = "https://onlyfans.com/";
    private static final String EXPORT_FORMAT = "ofbackup-auth";
    private static final int EXPORT_VERSION = 1;

    private WebView webView;
    private String pendingExport;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState != null) {
            pendingExport = savedInstanceState.getString("pendingExport");
        }
        setContentView(createLayout());
        configureWebView();
        if (savedInstanceState == null) {
            webView.loadUrl(LOGIN_URL);
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (pendingExport != null) {
            outState.putString("pendingExport", pendingExport);
        }
        if (webView != null) {
            webView.saveState(outState);
        }
    }

    private LinearLayout createLayout() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(20, 12, 20, 12);

        TextView notice = new TextView(this);
        notice.setText("Inicia sesión en esta ventana (con contraseña o mediante Google/Twitter). La app solo puede exportar la sesión creada dentro de su propio navegador.");
        notice.setTextSize(14);
        root.addView(notice, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);

        Button export = new Button(this);
        export.setText("Generar archivo");
        export.setOnClickListener(view -> exportSession());
        actions.addView(export, new LinearLayout.LayoutParams(0, -2, 1));

        Button clear = new Button(this);
        clear.setText("Borrar sesión");
        clear.setOnClickListener(view -> clearSession());
        actions.addView(clear, new LinearLayout.LayoutParams(0, -2, 1));
        root.addView(actions, new LinearLayout.LayoutParams(-1, -2));

        Button chooseAccount = new Button(this);
        chooseAccount.setText("Rellenar correo desde cuenta Google");
        chooseAccount.setOnClickListener(view -> chooseGoogleAccount());
        root.addView(chooseAccount, new LinearLayout.LayoutParams(-1, -2));

        webView = new WebView(this);
        root.addView(webView, new LinearLayout.LayoutParams(-1, 0, 1));
        return root;
    }

    private void configureWebView() {
        configureWebSettings(webView.getSettings());
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onCreateWindow(WebView view, boolean isDialog, boolean isUserGesture, android.os.Message resultMsg) {
                WebView newWebView = new WebView(MainActivity.this);
                configureWebSettings(newWebView.getSettings());
                newWebView.setWebViewClient(new WebViewClient() {
                    @Override
                    public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest request) {
                        String url = request.getUrl().toString();
                        if (isAllowedHost(request.getUrl().getHost())) {
                            webView.loadUrl(url);
                        }
                        return true;
                    }

                    @Override
                    public boolean shouldOverrideUrlLoading(WebView v, String url) {
                        if (isAllowedHost(Uri.parse(url).getHost())) {
                            webView.loadUrl(url);
                        }
                        return true;
                    }
                });

                WebView.WebViewTransport transport = (WebView.WebViewTransport) resultMsg.obj;
                transport.setWebView(newWebView);
                resultMsg.sendToTarget();
                return true;
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String host = request.getUrl().getHost();
                return !isAllowedHost(host);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                String host = Uri.parse(url).getHost();
                return !isAllowedHost(host);
            }
        });
    }

    private void configureWebSettings(WebSettings settings) {
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setSupportZoom(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(true);
        settings.setSupportMultipleWindows(true);

        // Sanitize User-Agent to prevent Google OAuth error 403 (disallowed_useragent)
        String userAgent = settings.getUserAgentString();
        if (userAgent != null) {
            String sanitized = userAgent.replace("; wv", "")
                    .replaceAll("Version/\\d+(\\.\\d+)*\\s*", "");
            settings.setUserAgentString(sanitized);
        }
    }

    private static boolean isAllowedHost(String host) {
        if (host == null) {
            return false;
        }
        String normalized = host.toLowerCase(Locale.US);

        // OnlyFans domains
        if (normalized.equals("onlyfans.com") || normalized.endsWith(".onlyfans.com")
                || normalized.equals("of.live") || normalized.endsWith(".of.live")) {
            return true;
        }

        // Google authentication & services domains
        if (normalized.equals("google.com") || normalized.endsWith(".google.com")
                || normalized.contains("google.")
                || normalized.equals("gstatic.com") || normalized.endsWith(".gstatic.com")
                || normalized.equals("googleapis.com") || normalized.endsWith(".googleapis.com")
                || normalized.equals("googleusercontent.com") || normalized.endsWith(".googleusercontent.com")
                || normalized.equals("recaptcha.net") || normalized.endsWith(".recaptcha.net")) {
            return true;
        }

        // Twitter / X authentication
        if (normalized.equals("twitter.com") || normalized.endsWith(".twitter.com")
                || normalized.equals("x.com") || normalized.endsWith(".x.com")
                || normalized.equals("twimg.com") || normalized.endsWith(".twimg.com")) {
            return true;
        }

        // Apple ID authentication
        if (normalized.equals("appleid.apple.com")) {
            return true;
        }

        return false;
    }

    private void exportSession() {
        CookieManager cookies = CookieManager.getInstance();
        cookies.flush();

        String script = "(function(){"
                + "var out = {cookie: '', storage: {}};"
                + "try { out.cookie = document.cookie || ''; } catch(e) {}"
                + "try {"
                + "  for (var i = 0; i < localStorage.length; i++) {"
                + "    var k = localStorage.key(i);"
                + "    if (k) out.storage[k] = localStorage.getItem(k);"
                + "  }"
                + "} catch(e) {}"
                + "try {"
                + "  for (var j = 0; j < sessionStorage.length; j++) {"
                + "    var sk = sessionStorage.key(j);"
                + "    if (sk) out.storage[sk] = sessionStorage.getItem(sk);"
                + "  }"
                + "} catch(e) {}"
                + "return JSON.stringify(out);"
                + "})()";

        webView.evaluateJavascript(script, result -> processExport(result));
    }

    private void processExport(String jsResult) {
        CookieManager cookies = CookieManager.getInstance();
        cookies.flush();

        Map<String, String> values = new LinkedHashMap<>();

        // 1. Gather cookies from CookieManager across all relevant OnlyFans URLs
        String currentUrl = webView.getUrl();
        String[] cookieUrls = {
                currentUrl != null ? currentUrl : "https://onlyfans.com/",
                "https://onlyfans.com/",
                "https://onlyfans.com",
                "https://.onlyfans.com",
                "https://www.onlyfans.com/",
                "https://api.onlyfans.com/",
                "https://static.onlyfans.com/",
                "https://static2.onlyfans.com/",
                "https://hub.onlyfans.com/"
        };
        for (String url : cookieUrls) {
            addCookies(values, cookies.getCookie(url));
        }

        // 2. Parse JS document.cookie and storage from DOM
        if (jsResult != null && !jsResult.isEmpty() && !"null".equals(jsResult)) {
            try {
                // If wrapped in string quotes from evaluateJavascript
                String unquoted = jsResult;
                if (unquoted.startsWith("\"") && unquoted.endsWith("\"")) {
                    JSONObject wrapper = new JSONObject("{\"val\":" + unquoted + "}");
                    unquoted = wrapper.getString("val");
                }
                JSONObject dom = new JSONObject(unquoted);
                String docCookie = dom.optString("cookie", "");
                addCookies(values, docCookie);

                JSONObject storage = dom.optJSONObject("storage");
                if (storage != null) {
                    addStorageValues(values, storage);
                }
            } catch (Exception ignored) {
            }
        }

        values.put("user_agent", webView.getSettings().getUserAgentString());

        // 3. Check for sess and auth_id
        String sess = values.get("sess");
        String authId = values.get("auth_id");

        if (sess == null || sess.trim().isEmpty() || authId == null || authId.trim().isEmpty()) {
            showMessage("No se ha detectado una sesión activa. Asegúrate de haber completado el login en OnlyFans.");
            return;
        }

        if (!authId.matches("[0-9]+")) {
            showMessage("La sesión devolvió un auth_id no válido (" + authId + ").");
            return;
        }

        // 4. Ensure x-bc is present: use extracted x-bc or generate deterministic client fingerprint
        String xBc = values.get("x-bc");
        if (xBc == null || xBc.trim().isEmpty()) {
            String userAgent = values.get("user_agent");
            xBc = computeSha1(authId + ":" + userAgent + ":" + sess);
            values.put("x-bc", xBc);
        }

        try {
            JSONObject auth = new JSONObject();
            auth.put("sess", values.get("sess"));
            auth.put("auth_id", values.get("auth_id"));
            auth.put("x-bc", values.get("x-bc"));
            auth.put("user_agent", values.get("user_agent"));

            JSONObject export = new JSONObject();
            export.put("format", EXPORT_FORMAT);
            export.put("version", EXPORT_VERSION);
            SimpleDateFormat timestamp = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US);
            timestamp.setTimeZone(TimeZone.getTimeZone("UTC"));
            export.put("created_at", timestamp.format(new Date()));
            export.put("auth", auth);
            pendingExport = export.toString(2);

            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("application/json");
            intent.putExtra(Intent.EXTRA_TITLE, "OFBackup-auth.json");
            startActivityForResult(intent, CREATE_EXPORT_FILE);
        } catch (JSONException exception) {
            showMessage("No se pudo preparar el archivo de sesión.");
        }
    }

    private void chooseGoogleAccount() {
        try {
            Intent chooser = AccountManager.newChooseAccountIntent(
                    null,
                    null,
                    new String[]{"com.google"},
                    "Selecciona el correo que quieres usar en OnlyFans",
                    null,
                    null,
                    null
            );
            startActivityForResult(chooser, CHOOSE_GOOGLE_ACCOUNT);
        } catch (RuntimeException exception) {
            showMessage("No se pudo abrir el selector de cuentas de Android.");
        }
    }

    private void fillEmailInWebView(String email) {
        String escapedEmail = JSONObject.quote(email);
        String script = "(function(){"
                + "var input=document.querySelector('input[type=email],input[autocomplete=email]');"
                + "if(!input){return false;}"
                + "var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;"
                + "setter.call(input," + escapedEmail + ");"
                + "input.dispatchEvent(new Event('input',{bubbles:true}));"
                + "input.dispatchEvent(new Event('change',{bubbles:true}));"
                + "return true;"
                + "})()";
        webView.evaluateJavascript(script, result -> {
            if ("false".equals(result)) {
                showMessage("No se encontró el campo de correo. Desplázate hasta el formulario de login.");
            } else {
                showMessage("Correo seleccionado. La contraseña se introduce en OnlyFans.");
            }
        });
    }

    private static void addCookies(Map<String, String> values, String header) {
        if (header == null || header.isEmpty()) return;
        for (String part : header.split(";")) {
            int separator = part.indexOf('=');
            if (separator <= 0) continue;
            String name = part.substring(0, separator).trim();
            String value = part.substring(separator + 1).trim();
            if (name.equals("sess") || name.equals("auth_id") || name.equals("x-bc") || name.equals("x_bc") || name.equals("bcToken")) {
                String targetKey = (name.equals("x_bc") || name.equals("bcToken")) ? "x-bc" : name;
                if (!values.containsKey(targetKey) || !values.get(targetKey).isEmpty()) {
                    values.put(targetKey, value);
                }
            }
        }
    }

    private static void addStorageValues(Map<String, String> values, JSONObject storage) {
        for (String key : new String[]{"sess", "auth_id", "auth_uid", "userId", "x-bc", "x_bc", "bcToken", "bc_token", "bc", "fp"}) {
            String val = storage.optString(key, "").trim();
            if (!val.isEmpty()) {
                if (key.equals("sess") && !values.containsKey("sess")) {
                    values.put("sess", val);
                } else if ((key.equals("auth_id") || key.equals("auth_uid") || key.equals("userId")) && !values.containsKey("auth_id")) {
                    values.put("auth_id", val);
                } else if ((key.equals("x-bc") || key.equals("x_bc") || key.equals("bcToken") || key.equals("bc_token") || key.equals("bc") || key.equals("fp")) && !values.containsKey("x-bc")) {
                    values.put("x-bc", val);
                }
            }
        }
    }

    private static String computeSha1(String input) {
        try {
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-1");
            byte[] digest = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (java.security.NoSuchAlgorithmException e) {
            return "0000000000000000000000000000000000000000";
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == CHOOSE_GOOGLE_ACCOUNT && resultCode == RESULT_OK && data != null) {
            String email = data.getStringExtra(AccountManager.KEY_ACCOUNT_NAME);
            if (email != null && !email.trim().isEmpty()) {
                fillEmailInWebView(email);
            }
            return;
        }
        if (requestCode != CREATE_EXPORT_FILE || resultCode != RESULT_OK || data == null || pendingExport == null) {
            return;
        }
        Uri destination = data.getData();
        if (destination == null) return;
        try (OutputStream output = getContentResolver().openOutputStream(destination)) {
            if (output == null) throw new IOException("No se pudo abrir el destino");
            output.write(pendingExport.getBytes(StandardCharsets.UTF_8));
            showMessage("Archivo guardado. Impórtalo en OF Downloader y ejecuta 'of probar'.");
        } catch (IOException exception) {
            showMessage("No se pudo guardar el archivo.");
        } finally {
            pendingExport = null;
        }
    }

    private void clearSession() {
        CookieManager.getInstance().removeAllCookies(ignored -> {
            CookieManager.getInstance().flush();
            webView.clearCache(true);
            webView.loadUrl(LOGIN_URL);
            showMessage("Sesión eliminada de esta app.");
        });
    }

    private void showMessage(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }
}
