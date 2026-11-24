package com.gorillastats.app

import android.content.ComponentName
import android.content.Context
import android.content.Intent

// Intents understood by the Tailscale Android app.
object Tailscale {
    const val PACKAGE = "com.tailscale.ipn"
    const val ACTION_CONNECT = "com.tailscale.ipn.CONNECT_VPN"
    const val ACTION_DISCONNECT = "com.tailscale.ipn.DISCONNECT_VPN"
    val ACTIVITY = ComponentName(PACKAGE, "$PACKAGE.AutomationActivity")
    val RECEIVER = ComponentName(PACKAGE, "$PACKAGE.IPNReceiver")

    // A broadcast works while the app is being destroyed, unlike starting an activity.
    fun sendBroadcast(context: Context, action: String) {
        try {
            context.sendBroadcast(Intent(action).setComponent(RECEIVER))
        } catch (_: Exception) {
        }
    }

    fun disconnect(context: Context) = sendBroadcast(context, ACTION_DISCONNECT)
}
