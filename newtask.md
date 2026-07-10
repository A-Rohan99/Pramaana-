# Satark Setu: Future Expansion Roadmap

This document outlines the detailed development stages for expanding Satark Setu into a comprehensive, highly accessible, and proactive security platform.

---

## 🗺️ Staged Implementation Phases

### 🔹 Phase 1: UPI & Bank Account VPA Scanner
*Focus: Intercepting financial transactions before users transfer money.*

- [ ] **1.1 VPA Extraction Engine**
  - Implement regular expression matching and NLP extraction for UPI IDs (`username@bank` format) and bank account details (IFSC + Account Number combinations) inside `preprocess.py`.
- [ ] **1.2 Threat Evaluation Layer**
  - Create a logic module to flag suspicious UPI handles:
    - Check for lookalike domains trying to mimic official agencies (e.g. `pmkisan-gov@axis` or `sbi-kyc@upi` when owned by private citizens).
    - Query known spam UPI databases or local blocklists.
- [ ] **1.3 UI Integration**
  - Update `index.html` to render flagged UPI VPAs with visual warning labels (e.g., ⚠️ *Lookalike government UPI handle detected*).

---

### 🔹 Phase 2: "Mukhaut" — Voice Verdict Output (TTS)
*Focus: Improving accessibility for low-literacy, elderly, and rural users.*

- [ ] **2.1 Text-to-Speech (TTS) Engine Integration**
  - Setup a local or cloud-based Hindi/Telugu TTS library (e.g., gTTS or local model integration).
- [ ] **2.2 Spoken Verdict Synthesis**
  - Create a template engine in `translate.py` that translates technical threat reports into simple spoken warnings (e.g., *"This message is a scam trying to steal your bank details. Do not share your OTP or PIN."*).
- [ ] **2.3 Audio Playback UI**
  - Add a "Listen to Verdict" (सुनें / వినండి) button next to the safety stamp on the frontend, streaming the generated audio file dynamically.

---

### 🔹 Phase 3: WhatsApp Forwarding Gateway Bot
*Focus: Meeting the users directly inside their primary messaging channel.*

- [ ] **3.1 Webhook & API Setup**
  - Build a webhook endpoint (`POST /api/whatsapp-webhook`) in `api.py` to receive forwarded text messages, screenshots, and voice notes.
- [ ] **3.2 WhatsApp Business API / Twilio Integration**
  - Integrate a client library to send dynamic replies back to the user on WhatsApp.
- [ ] **3.3 Media Downloader & Pipeline Connection**
  - Implement a mechanism to download media files (images, audio notes) from WhatsApp and feed them straight into the Satark Setu OCR & Whisper pipelines.
- [ ] **3.4 Emoji & Short-Audio Reply Generator**
  - Format WhatsApp responses cleanly using safety colored circles (🟢/🟡/🔴) and forward the Phase 2 TTS audio notes back to WhatsApp.

---

### 🔹 Phase 4: Adversarial OCR Normalization
*Focus: Evading obfuscation tricks used by professional scammers.*

- [ ] **4.1 Character De-obfuscation Layer**
  - Build a mapping dictionary and regex parser in `normalize.py` to decode typical evasion strings:
    - Obfuscated keywords: `K-Y-C`, `K.Y.C`, `S_B_I`, `§BI`, `P-M-K-I-S-A-N`.
    - Homoglyphs: Substituting English characters with lookalike Greek or Cyrillic characters.
- [ ] **4.2 Advanced Visual Text Segmentation**
  - Fine-tune OCR parameters to segment text printed over complex backgrounds, noisy gradients, or inside fake bank banner layouts.

---

### 🔹 Phase 5: Crowdsourced Fraud Registry & Geo-Hotspots
*Focus: Shifting from a reactive checker to a proactive community radar.*

- [ ] **5.1 Report Incident Endpoint**
  - Add a "Report this Scam" button on the UI, allowing users to submit confirmed threats to a local ledger.
- [ ] **5.2 Database Schema for Telemetry**
  - Design a database table (e.g., in SQLite or PostgreSQL) tracking reported domains, phone numbers, and UPI handles with a coarse region tag (e.g., state or district).
- [ ] **5.3 Regional Alert Dashboard**
  - Build a visual dashboard section on the website showing "Trending Scams in your Region" to raise local awareness.
