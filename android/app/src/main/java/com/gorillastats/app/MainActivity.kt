package com.gorillastats.app

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat

class MainActivity : ComponentActivity() {
    private lateinit var webView: WebView
    private lateinit var overlay: LinearLayout
    private lateinit var statusText: TextView
    private lateinit var retryButton: Button

    private val handler = Handler(Looper.getMainLooper())
    private val appHost: String? = Uri.parse(BuildConfig.APP_URL).host
    private var attempts = 0
    private var failed = false
    private var vpnWasActive = false
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    private val fileChooser =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            fileCallback?.onReceiveValue(
                WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data)
            )
            fileCallback = null
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowCompat.getInsetsController(window, window.decorView).isAppearanceLightStatusBars = false
        setContentView(buildContent())

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })

        // When a VPN is already active we assume it is Tailscale and leave it alone, also on exit.
        vpnWasActive = isVpnActive()
        if (!vpnWasActive) connectTailscale()
        load()
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (isFinishing && BuildConfig.DISCONNECT_ON_EXIT && !vpnWasActive) disconnectTailscale()
        (webView.parent as? ViewGroup)?.removeView(webView)
        webView.destroy()
        super.onDestroy()
    }

    private fun load() {
        webView.loadUrl(BuildConfig.APP_URL)
    }

    private fun onLoadFailed() {
        failed = true
        if (attempts++ < MAX_ATTEMPTS) {
            showOverlay(R.string.connecting, retry = false)
            handler.postDelayed({ load() }, RETRY_DELAY_MS)
        } else {
            showOverlay(R.string.unreachable, retry = true)
        }
    }

    private fun showOverlay(message: Int, retry: Boolean) {
        statusText.setText(message)
        retryButton.visibility = if (retry) View.VISIBLE else View.GONE
        overlay.visibility = View.VISIBLE
    }

    private fun isVpnActive(): Boolean {
        val manager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val capabilities = manager.getNetworkCapabilities(manager.activeNetwork) ?: return false
        return capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
    }

    // Tailscale's AutomationActivity is a transparent trampoline meant for external automation.
    private fun connectTailscale() {
        try {
            startActivity(
                Intent(ACTION_CONNECT).setClassName(TAILSCALE_PACKAGE, "$TAILSCALE_PACKAGE.AutomationActivity")
            )
        } catch (_: Exception) {
            // Tailscale missing or intent rejected: the app still opens and shows the retry screen.
        }
    }

    // A broadcast works while we are being destroyed, unlike starting an activity.
    private fun disconnectTailscale() {
        try {
            sendBroadcast(Intent(ACTION_DISCONNECT).setPackage(TAILSCALE_PACKAGE))
        } catch (_: Exception) {
        }
    }

    private fun buildContent(): View {
        val root = FrameLayout(this).apply { setBackgroundColor(BACKGROUND) }
        webView = WebView(this).apply {
            setBackgroundColor(BACKGROUND)
            configure(this)
        }
        root.addView(webView, FrameLayout.LayoutParams(MATCH, MATCH))

        statusText = TextView(this).apply {
            setTextColor(TEXT)
            textSize = 18f
            gravity = Gravity.CENTER
            setText(R.string.connecting)
        }
        retryButton = Button(this).apply {
            setText(R.string.retry)
            visibility = View.GONE
            setOnClickListener {
                attempts = 0
                showOverlay(R.string.connecting, retry = false)
                if (!isVpnActive()) connectTailscale()
                load()
            }
        }
        overlay = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(BACKGROUND)
            setPadding(48, 48, 48, 48)
            isClickable = true
            addView(statusText, LinearLayout.LayoutParams(MATCH, WRAP).apply { bottomMargin = 32 })
            addView(retryButton, LinearLayout.LayoutParams(WRAP, WRAP))
        }
        root.addView(overlay, FrameLayout.LayoutParams(MATCH, MATCH))

        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        return root
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configure(view: WebView) {
        view.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            setSupportZoom(false)
        }
        view.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                failed = false
            }

            override fun onPageFinished(view: WebView, url: String?) {
                if (!failed) {
                    attempts = 0
                    overlay.visibility = View.GONE
                }
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) onLoadFailed()
            }

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (request.url.host == appHost) return false
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, request.url))
                } catch (_: ActivityNotFoundException) {
                }
                return true
            }
        }
        view.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView,
                callback: ValueCallback<Array<Uri>>,
                params: FileChooserParams,
            ): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                return try {
                    fileChooser.launch(params.createIntent())
                    true
                } catch (_: ActivityNotFoundException) {
                    fileCallback = null
                    false
                }
            }
        }
    }

    private companion object {
        const val TAILSCALE_PACKAGE = "com.tailscale.ipn"
        const val ACTION_CONNECT = "com.tailscale.ipn.CONNECT_VPN"
        const val ACTION_DISCONNECT = "com.tailscale.ipn.DISCONNECT_VPN"
        const val MAX_ATTEMPTS = 20
        const val RETRY_DELAY_MS = 1500L
        const val MATCH = ViewGroup.LayoutParams.MATCH_PARENT
        const val WRAP = ViewGroup.LayoutParams.WRAP_CONTENT
        val BACKGROUND = Color.parseColor("#0D140E")
        val TEXT = Color.parseColor("#F8F9FA")
    }
}
