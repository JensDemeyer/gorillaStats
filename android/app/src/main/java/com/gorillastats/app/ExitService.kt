package com.gorillastats.app

import android.app.Service
import android.content.Intent
import android.os.Binder
import android.os.IBinder

// Swiping the app away from the recent apps list does not reliably call Activity.onDestroy.
// A service that lives as long as the app is told about it through onTaskRemoved, so Tailscale
// can still be switched off. MainActivity both starts and binds it: only a started service is
// told about the removed task, and the binding keeps it from being stopped in the background.
class ExitService : Service() {
    override fun onBind(intent: Intent?): IBinder = Binder()

    override fun onTaskRemoved(rootIntent: Intent?) {
        if (disconnectOnClose) {
            disconnectOnClose = false
            Tailscale.disconnect(this)
        }
        stopSelf()
        super.onTaskRemoved(rootIntent)
    }

    companion object {
        // Set by MainActivity: true when we started Tailscale ourselves and may stop it again.
        @Volatile
        var disconnectOnClose = false
    }
}
