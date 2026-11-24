package com.modgarage.studio;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import android.provider.OpenableColumns;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.os.Build;
import android.provider.MediaStore;
import java.io.OutputStream;
import android.util.Base64;

public class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST = 4102;
    private static final int SAVE_FILE_REQUEST = 4103;
    private static final String SITE_URL = "https://most-wanted-mod-studio.lovable.app";
    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;
    private byte[] pendingDownloadBytes;
    private String pendingDownloadMime = "application/zip";

    public class DownloadBridge {
        @JavascriptInterface
        public void saveBase64File(String filename, String base64, String mimeType) {
            try {
                pendingDownloadBytes = Base64.decode(base64, Base64.DEFAULT);
                pendingDownloadMime = (mimeType == null || mimeType.isEmpty()) ? "application/octet-stream" : mimeType;
                runOnUiThread(() -> {
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType(pendingDownloadMime);
                    intent.putExtra(Intent.EXTRA_TITLE, filename == null || filename.isEmpty() ? "mod-garage-export.zip" : filename);
                    startActivityForResult(intent, SAVE_FILE_REQUEST);
                });
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Gagal menyiapkan file ZIP", Toast.LENGTH_LONG).show());
            }
        }
    }

    private void installBlobDownloadHandler(WebView view) {
        String script = "(function(){if(window.__garageDownloadHook)return;window.__garageDownloadHook=true;" +
            "document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[download]');" +
            "if(!a||!a.href||!a.href.startsWith('blob:'))return;e.preventDefault();e.stopImmediatePropagation();" +
            "var name=a.getAttribute('download')||'mod-garage-export.zip';" +
            "fetch(a.href).then(function(r){return r.blob()}).then(function(b){" +
            "var reader=new FileReader();reader.onloadend=function(){var s=reader.result||'';var p=s.indexOf(',');" +
            "if(p>=0&&window.AndroidDownload)AndroidDownload.saveBase64File(name,s.substring(p+1),b.type||'application/zip');};" +
            "reader.readAsDataURL(b);}).catch(function(){alert('Gagal menyiapkan unduhan. Coba ekspor ulang.');});" +
            "},true);})();";
        view.evaluateJavascript(script, null);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(0xFF10131A);
        getWindow().setNavigationBarColor(0xFF10131A);

        webView = new WebView(this);
        webView.setBackgroundColor(0xFF10131A);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setLoadsImagesAutomatically(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        webView.addJavascriptInterface(new DownloadBridge(), "AndroidDownload");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return false;
            }
            @Override
            public void onPageFinished(WebView view, String url) {
                installBlobDownloadHandler(view);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                    FileChooserParams params) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (Exception e) {
                    filePathCallback = null;
                    Toast.makeText(MainActivity.this, "Tidak dapat membuka pemilih file", Toast.LENGTH_LONG).show();
                    return false;
                }
            }
        });

        setContentView(webView);
        if (savedInstanceState == null) webView.loadUrl(SITE_URL);
        else webView.restoreState(savedInstanceState);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST && filePathCallback != null) {
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    results = new Uri[count];
                    for (int i = 0; i < count; i++) results[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) results = new Uri[] { data.getData() };
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        } else if (requestCode == SAVE_FILE_REQUEST) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null && pendingDownloadBytes != null) {
                try (OutputStream out = getContentResolver().openOutputStream(data.getData())) {
                    if (out == null) throw new Exception("Output stream unavailable");
                    out.write(pendingDownloadBytes);
                    out.flush();
                    Toast.makeText(this, "Paket ZIP berhasil disimpan ke telepon", Toast.LENGTH_LONG).show();
                } catch (Exception e) {
                    Toast.makeText(this, "Gagal menyimpan paket ZIP", Toast.LENGTH_LONG).show();
                }
            }
            pendingDownloadBytes = null;
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (webView != null) webView.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (filePathCallback != null) {
            filePathCallback.onReceiveValue(null);
            filePathCallback = null;
        }
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}