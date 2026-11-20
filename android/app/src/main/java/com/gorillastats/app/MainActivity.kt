package com.gorillastats.app

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.SystemClock
import android.view.ViewGroup
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import com.gorillastats.app.LoadingView.State
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {
    private lateinit var webView: WebView
    private lateinit var loading: LoadingView

    private val worker = Executors.newSingleThreadExecutor()
    private val appUri: Uri = Uri.parse(BuildConfig.APP_URL)
    private val appHost: String? = appUri.host
    private val appPort: Int = if (appUri.port != -1) appUri.port else if (appUri.scheme == "https") 443 else 80
    private var generation = 0
    private var loadFailures = 0
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
                if (!loading.isShowing && webView.canGoBack()) webView.goBack() else finish()
            }
        })

        // When a VPN is already active we assume it is Tailscale and leave it alone, also on exit.
        vpnWasActive = isVpnActive()
        connectAndLoad()
    }

    override fun onDestroy() {
        generation++
        worker.shutdownNow()
        if (isFinishing && BuildConfig.DISCONNECT_ON_EXIT && !vpnWasActive) disconnectTailscale()
        (webView.parent as? ViewGroup)?.removeView(webView)
        webView.destroy()
        super.onDestroy()
    }

    // Starts Tailscale if needed, then waits (off the main thread) until the Pi accepts connections.
    // Probing first avoids WebView hanging for minutes on a dead route before it reports an error.
    private fun connectAndLoad() {
        val run = ++generation
        webView.stopLoading()
        loading.reset()
        val vpnUp = isVpnActive()
        if (vpnUp) {
            loading.setStep(STEP_VPN, State.DONE)
            loading.setStep(STEP_PI, State.ACTIVE)
        } else {
            loading.setStep(STEP_VPN, State.ACTIVE)
            connectTailscale()
        }
        worker.execute {
            val start = SystemClock.elapsedRealtime()
            var vpnShown = vpnUp
            var resends = 0
            while (run == generation) {
                if (!vpnShown && isVpnActive()) {
                    vpnShown = true
                    ui(run) {
                        loading.setStep(STEP_VPN, State.DONE)
                        loading.setStep(STEP_PI, State.ACTIVE)
                    }
                }
                if (isReachable()) {
                    ui(run) {
                        loading.setStep(STEP_VPN, State.DONE)
                        loading.setStep(STEP_PI, State.DONE)
                        loading.setStep(STEP_APP, State.ACTIVE)
                        webView.loadUrl(BuildConfig.APP_URL)
                    }
                    return@execute
                }
                val elapsed = SystemClock.elapsedRealtime() - start
                if (elapsed > CONNECT_TIMEOUT_MS) break
                if (resends < MAX_RESENDS && elapsed > (resends + 1) * RESEND_AFTER_MS && !isVpnActive()) {
                    resends++
                    ui(run) { connectTailscale() }
                }
                try {
                    Thread.sleep(PROBE_INTERVAL_MS)
                } catch (_: InterruptedException) {
                    return@execute
                }
            }
            ui(run) { showConnectionFailure() }
        }
    }

    private fun ui(run: Int, action: () -> Unit) = runOnUiThread { if (run == generation) action() }

    private fun showConnectionFailure() {
        if (!isVpnActive()) {
            loading.setStep(STEP_VPN, State.FAILED)
            loading.showError(R.string.error_vpn_title, R.string.error_vpn_message)
        } else {
            loading.setStep(STEP_VPN, State.DONE)
            loading.setStep(STEP_PI, State.FAILED)
            loading.showError(R.string.error_pi_title, R.string.error_pi_message)
        }
    }

    private fun isReachable(): Boolean = try {
        Socket().use { it.connect(InetSocketAddress(appHost, appPort), PROBE_TIMEOUT_MS) }
        true
    } catch (_: Exception) {
        false
    }

    private fun onLoadFailed() {
        failed = true
        if (loadFailures++ < MAX_LOAD_FAILURES) {
            connectAndLoad()
        } else {
            generation++
            loading.setStep(STEP_APP, State.FAILED)
            loading.showError(R.string.error_app_title, R.string.error_app_message)
        }
    }

    private fun isVpnActive(): Boolean {
        val manager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val capabilities = manager.getNetworkCapabilities(manager.activeNetwork) ?: return false
        return capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
    }

    // Newer Tailscale builds have a transparent AutomationActivity for this; older builds only
    // have the exported IPNReceiver broadcast, which is what we fall back to.
    private fun connectTailscale() {
        try {
            startActivity(Intent(ACTION_CONNECT).setComponent(TAILSCALE_ACTIVITY))
        } catch (_: Exception) {
            sendTailscaleBroadcast(ACTION_CONNECT)
        }
    }

    // A broadcast works while we are being destroyed, unlike starting an activity.
    private fun disconnectTailscale() = sendTailscaleBroadcast(ACTION_DISCONNECT)

    private fun sendTailscaleBroadcast(action: String) {
        try {
            sendBroadcast(Intent(action).setComponent(TAILSCALE_RECEIVER))
        } catch (_: Exception) {
        }
    }

    private fun openTailscale() {
        val launch = packageManager.getLaunchIntentForPackage(TAILSCALE_PACKAGE) ?: return
        try {
            startActivity(launch)
        } catch (_: Exception) {
        }
    }

    private fun buildContent(): FrameLayout {
        val root = FrameLayout(this).apply { setBackgroundColor(BACKGROUND) }
        webView = WebView(this).apply {
            setBackgroundColor(BACKGROUND)
            configure(this)
        }
        root.addView(webView, FrameLayout.LayoutParams(MATCH, MATCH))

        loading = LoadingView(this).apply {
            onRetry = {
                loadFailures = 0
                connectAndLoad()
            }
            onOpenTailscale = { openTailscale() }
        }
        root.addView(loading, FrameLayout.LayoutParams(MATCH, MATCH))

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
                if (!failed && loading.isShowing) {
                    loadFailures = 0
                    loading.complete()
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
            override fun onProgressChanged(view: WebView, newProgress: Int) {
                if (loading.isShowing) loading.setLoadPercent(newProgress)
            }

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
        val TAILSCALE_ACTIVITY = ComponentName(TAILSCALE_PACKAGE, "$TAILSCALE_PACKAGE.AutomationActivity")
        val TAILSCALE_RECEIVER = ComponentName(TAILSCALE_PACKAGE, "$TAILSCALE_PACKAGE.IPNReceiver")
        const val STEP_VPN = 0
        const val STEP_PI = 1
        const val STEP_APP = 2
        const val CONNECT_TIMEOUT_MS = 30_000L
        const val RESEND_AFTER_MS = 8_000L
        const val MAX_RESENDS = 2
        const val PROBE_INTERVAL_MS = 1_000L
        const val PROBE_TIMEOUT_MS = 1_500
        const val MAX_LOAD_FAILURES = 2
        const val MATCH = ViewGroup.LayoutParams.MATCH_PARENT
        val BACKGROUND = Color.parseColor("#0D140E")
    }
}
