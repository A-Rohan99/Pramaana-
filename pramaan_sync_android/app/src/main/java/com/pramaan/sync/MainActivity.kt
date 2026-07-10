package com.pramaan.sync

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {

    private lateinit var urlInput: EditText
    private lateinit var deviceInput: EditText
    private lateinit var statusText: TextView
    private val SMS_PERMISSION_CODE = 101

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Programmatic premium dark mode layout matching Pramaan web aesthetics
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            backgroundColor = Color.parseColor("#0F172A") // slate-900
            setPadding(60, 80, 60, 80)
            gravity = Gravity.CENTER_HORIZONTAL
        }

        // Header Title
        val titleText = TextView(this).apply {
            text = "PRAMAAN SYNC"
            setTextColor(Color.parseColor("#2DD4BF")) // teal-400
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f)
            typeface = Typeface.create("sans-serif-medium", Typeface.BOLD)
            gravity = Gravity.CENTER
            setPadding(0, 0, 0, 10)
        }
        root.addView(titleText)

        // Subtitle description
        val subText = TextView(this).apply {
            text = "Companion app to forward bank SMS alerts to your local Pramaan ledger in real-time."
            setTextColor(Color.parseColor("#94A3B8")) // slate-400
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            gravity = Gravity.CENTER
            setPadding(0, 0, 0, 60)
        }
        root.addView(subText)

        // Input Card block
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            backgroundColor = Color.parseColor("#1E293B") // slate-800
            setPadding(40, 40, 40, 40)
            gravity = Gravity.LEFT
            // Round corners layout drawable
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#1E293B"))
                cornerRadius = 24f
                setStroke(2, Color.parseColor("#334155")) // border-slate-700
            }
        }

        // Label for webhook URL
        val urlLabel = TextView(this).apply {
            text = "Webhook URL (Laptop IP)"
            setTextColor(Color.parseColor("#F1F5F9"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            typeface = Typeface.DEFAULT_BOLD
            setPadding(0, 0, 0, 12)
        }
        card.addView(urlLabel)

        // Webhook URL Edit Text
        urlInput = EditText(this).apply {
            hint = "http://192.168.0.140:8000/api/sms-webhook"
            setHintTextColor(Color.parseColor("#475569"))
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#0F172A"))
                cornerRadius = 16f
                setStroke(2, Color.parseColor("#334155"))
            }
            setPadding(30, 26, 30, 26)
        }
        card.addView(urlInput)

        // Label for Device Name
        val deviceLabel = TextView(this).apply {
            text = "Device Name Identifier"
            setTextColor(Color.parseColor("#F1F5F9"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            typeface = Typeface.DEFAULT_BOLD
            setPadding(0, 30, 0, 12)
        }
        card.addView(deviceLabel)

        // Device name Input
        deviceInput = EditText(this).apply {
            hint = "MyAndroidPhone"
            setHintTextColor(Color.parseColor("#475569"))
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#0F172A"))
                cornerRadius = 16f
                setStroke(2, Color.parseColor("#334155"))
            }
            setPadding(30, 26, 30, 26)
        }
        card.addView(deviceInput)

        root.addView(card)

        // Status Card
        statusText = TextView(this).apply {
            text = "Status: Checking permissions..."
            setTextColor(Color.parseColor("#94A3B8"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setPadding(0, 40, 0, 40)
            gravity = Gravity.CENTER
        }
        root.addView(statusText)

        // Action Buttons layout
        val buttonRow = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        }

        // Save and Test button
        val saveBtn = Button(this).apply {
            text = "Test & Save Connection"
            setTextColor(Color.BLACK)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            typeface = Typeface.DEFAULT_BOLD
            isAllCaps = false
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#2DD4BF")) // teal-400
                cornerRadius = 20f
            }
            setPadding(0, 30, 0, 30)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 0, 0, 24)
            }
            setOnClickListener {
                saveAndTestConnection()
            }
        }
        buttonRow.addView(saveBtn)

        // Permission solicitors
        val permBtn = Button(this).apply {
            text = "Grant SMS Permissions"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            typeface = Typeface.DEFAULT_BOLD
            isAllCaps = false
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#334155")) // slate-700
                cornerRadius = 20f
            }
            setPadding(0, 30, 0, 30)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            setOnClickListener {
                requestSmsPermission()
            }
        }
        buttonRow.addView(permBtn)

        root.addView(buttonRow)

        setContentView(root)

        // Retrieve saved values
        val prefs = getSharedPreferences("PramaanPrefs", Context.MODE_PRIVATE)
        urlInput.setText(prefs.getString("webhook_url", ""))
        deviceInput.setText(prefs.getString("device_name", "AndroidPhone"))

        checkPermissions()
    }

    private fun checkPermissions() {
        val readSms = ContextCompat.checkSelfPermission(this, Manifest.permission.RECEIVE_SMS)
        if (readSms == PackageManager.PERMISSION_GRANTED) {
            statusText.text = "Status: SMS Gateway Active (Permissions Granted)"
            statusText.setTextColor(Color.parseColor("#4ADE80")) // green-400
        } else {
            statusText.text = "Status: SMS Permission Needed (Gateway Disabled)"
            statusText.setTextColor(Color.parseColor("#F87171")) // red-400
        }
    }

    private fun requestSmsPermission() {
        ActivityCompat.requestPermissions(
            this,
            arrayOf(Manifest.permission.RECEIVE_SMS),
            SMS_PERMISSION_CODE
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == SMS_PERMISSION_CODE) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                statusText.text = "Status: SMS Gateway Active (Permissions Granted)"
                statusText.setTextColor(Color.parseColor("#4ADE80"))
                Toast.makeText(this, "SMS Permission Granted", Toast.LENGTH_SHORT).show()
            } else {
                statusText.text = "Status: SMS Permission Denied"
                statusText.setTextColor(Color.parseColor("#F87171"))
                Toast.makeText(this, "SMS Permission Required for Real-time Auto-Sync", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun saveAndTestConnection() {
        val urlStr = urlInput.text.toString().trim()
        val deviceStr = deviceInput.text.toString().trim()

        if (urlStr.isEmpty()) {
            Toast.makeText(this, "Please enter a Webhook URL", Toast.LENGTH_SHORT).show()
            return
        }

        // Save to preferences immediately
        val prefs = getSharedPreferences("PramaanPrefs", Context.MODE_PRIVATE)
        prefs.edit().apply {
            putString("webhook_url", urlStr)
            putString("device_name", deviceStr)
            apply()
        }

        statusText.text = "Status: Testing endpoint connection..."
        statusText.setTextColor(Color.parseColor("#FBBF24")) // amber-400

        thread {
            var conn: HttpURLConnection? = null
            var success = false
            var errorMsg = ""
            try {
                val url = URL(urlStr)
                conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("X-Device-Name", deviceStr)
                conn.doOutput = true
                conn.connectTimeout = 4000
                conn.readTimeout = 4000

                // Send a test message payload
                val json = JSONObject().apply {
                    put("from", "PramaanCompanionTest")
                    put("message", "Sync companion test connection")
                    put("receivedAt", System.currentTimeMillis())
                }

                val wr = OutputStreamWriter(conn.outputStream)
                wr.write(json.toString())
                wr.flush()
                wr.close()

                val responseCode = conn.responseCode
                success = (responseCode == 200)
                if (!success) {
                    errorMsg = "HTTP Status: $responseCode"
                }
            } catch (e: Exception) {
                errorMsg = e.message ?: "Connection Timeout"
            } finally {
                conn?.disconnect()
            }

            runOnUiThread {
                if (success) {
                    statusText.text = "Status: Connected successfully to Pramaan!"
                    statusText.setTextColor(Color.parseColor("#4ADE80"))
                    Toast.makeText(this@MainActivity, "Connection Active!", Toast.LENGTH_SHORT).show()
                } else {
                    statusText.text = "Status: Connection failed ($errorMsg)"
                    statusText.setTextColor(Color.parseColor("#F87171"))
                    Toast.makeText(this@MainActivity, "Could not reach laptop. Check IP/WiFi.", Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}
