package com.pramaan.sync

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import kotlin.concurrent.thread

class SmsReceiver : BroadcastReceiver() {
    private val TAG = "PramaanSmsReceiver"

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent)
        for (sms in messages) {
            val sender = sms.displayOriginatingAddress ?: "Unknown"
            val body = sms.messageBody ?: ""
            Log.d(TAG, "Received SMS from: $sender: $body")

            // Local filtering matching bank transactions
            val lowerBody = body.lowercase(Locale.getDefault())
            val matches = lowerBody.contains("credited") || 
                          lowerBody.contains("debited") || 
                          lowerBody.contains("upi") || 
                          lowerBody.contains("payment") || 
                          lowerBody.contains("rs") || 
                          lowerBody.contains("received") || 
                          lowerBody.contains("paid")

            if (matches) {
                // Fetch saved Webhook URL from SharedPreferences
                val prefs = context.getSharedPreferences("PramaanPrefs", Context.MODE_PRIVATE)
                val webhookUrl = prefs.getString("webhook_url", "") ?: ""
                val deviceName = prefs.getString("device_name", "AndroidPhone") ?: "AndroidPhone"

                if (webhookUrl.isNotEmpty()) {
                    Log.d(TAG, "Forwarding matching SMS to $webhookUrl")
                    forwardSms(webhookUrl, deviceName, sender, body)
                } else {
                    Log.d(TAG, "No Webhook URL configured in preferences. Skipping.")
                }
            } else {
                Log.d(TAG, "SMS did not match transaction keywords. Ignored.")
            }
        }
    }

    private fun forwardSms(targetUrl: String, deviceName: String, sender: String, message: String) {
        thread {
            var conn: HttpURLConnection? = null
            try {
                val url = URL(targetUrl)
                conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("X-Device-Name", deviceName)
                conn.doOutput = true
                conn.connectTimeout = 5000
                conn.readTimeout = 5000

                // JSON payload matching Pramaan backend expected formats
                val json = JSONObject().apply {
                    put("from", sender)
                    put("message", message)
                    put("receivedAt", System.currentTimeMillis())
                }

                val wr = OutputStreamWriter(conn.outputStream)
                wr.write(json.toString())
                wr.flush()
                wr.close()

                val responseCode = conn.responseCode
                Log.d(TAG, "Server responded with HTTP code: $responseCode")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to forward SMS to local network: ${e.message}")
            } finally {
                conn?.disconnect()
            }
        }
    }
}
