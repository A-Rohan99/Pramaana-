# Pramaan Sync — Android Companion App Codebase

This is the official native companion Android application for **Pramaan**. It acts as a real-time bridge that securely intercept bank SMS alerts on your mobile phone and pushes them directly into the Pramaan fraud-detection and bookkeeping pipeline.

---

## Key Features

1. **Local Network HTTP Posting**: Automatically resolves your laptop's local IP address and submits payloads directly over local WiFi.
2. **Local Keyword Filter**: Runs basic text parsing locally (`credited`, `debited`, `UPI`, `Rs`, `payment`) so private, personal chats never leave your device.
3. **Dynamic Permissions Manager**: Easily requests standard Android SMS permissions at runtime with visual feedback.
4. **Test Endpoint Pinger**: Includes a programmatic testing routine that lets you ping the Pramaan uvicorn server and check response codes before activating sync.
5. **Modern Dark Theme UI**: Custom programmatic layout matching Pramaan’s glassmorphic design system.

---

## How to Import & Build in Android Studio

1. Open **Android Studio**.
2. Select **File > Open** (or import project).
3. Navigate to the `pramaan_sync_android/` folder in this repository and select it.
4. Android Studio will automatically resolve Gradle dependencies.
5. Connect your Android phone with **USB Debugging** enabled.
6. Press the green **Run (Play)** button in Android Studio to compile and deploy the APK onto your device!

---

## Technical Details

- **Language**: Kotlin 1.8.0
- **Android Target**: SDK 33 (Android 13)
- **Minimum Target**: SDK 21 (Android 5.0 - runs on virtually all active Android devices)
- **Network Stack**: Built-in `HttpURLConnection` on background threads (zero overhead, fully secure).
