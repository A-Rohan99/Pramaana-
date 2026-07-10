import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update English translations (add Monthly Narrative, AI Chat chips, Inventory placeholders)
en_old = '''    recordUpdateBtn:"Record & Update Stock",addEditItem:"+ Add / Edit Item",
    // AI Intelligence
    aiIntelTitle:"AI Decision Intelligence",'''
en_new = '''    recordUpdateBtn:"Record & Update Stock",addEditItem:"+ Add / Edit Item",
    // Monthly Narrative & AI Chat & etc.
    narrativeSectionTitle:"📊 Monthly Business Summary",
    narrativeSectionSub:"Your AI accountant's take on this month's numbers — in plain language, not spreadsheet jargon.",
    accountantsNote:"📝 Accountant's Note",narrativeRefresh:"Refresh",
    narrativePlaceholder:"Click Refresh to generate your monthly narrative…",
    expenseBreakdown:"🗂️ Expense Breakdown",noExpenseData:"No expense data yet.",
    chatQ1:"Who owes me most?",chatQ2:"Profit this month?",chatQ3:"Biggest expenses?",chatQ4:"Supplier owed most?",
    chatPlaceholder:"e.g. Am I spending more on rice or dal this month?",
    chatAsk:"Ask",
    reliabilityLabel:"Reliability",priceStabilityLabel:"Price Stability",
    ordersLabel:"orders",totalLabel:"Total:",
    noPriorityActions:"No priority actions — your business looks healthy!",
    noNegativeTrends:"No negative trends detected.",
    noPricingData:"No pricing optimizations yet. Add inventory and sales data.",
    noDemandData:"No demand data yet.",
    noPurchaseData:"No purchase recommendations yet.",
    noSupplierData:"No supplier history yet. Record purchases to see scores.",
    noPromoData:"No promotion recommendations yet.",
    noBundleData:"No bundle suggestions yet.",
    noLeakageData:"✅ No significant leakage detected. Business looks tight!",
    noRecoveryData:"Nothing urgent right now.",
    copilotThinking:"Thinking…",copilotError:"Error contacting AI. Please try again.",
    copilotModeWhatIf:"🔮 What-If Simulation",copilotModeRootCause:"🔍 Root Cause Analysis",copilotModeStandard:"💬 AI Copilot",
    // AI Intelligence
    aiIntelTitle:"AI Decision Intelligence",'''
content = content.replace(en_old, en_new)

# 2. Update Hindi translations
hi_old = '''    recordUpdateBtn:"रिकॉर्ड करें और स्टॉक अपडेट करें",addEditItem:"+ वस्तु जोड़ें / संपादित करें",
    // AI Intelligence
    aiIntelTitle:"AI निर्णय बुद्धिमत्ता",'''
hi_new = '''    recordUpdateBtn:"रिकॉर्ड करें और स्टॉक अपडेट करें",addEditItem:"+ वस्तु जोड़ें / संपादित करें",
    narrativeSectionTitle:"📊 मासिक व्यापार सारांश",
    narrativeSectionSub:"आपके AI लेखाकार का इस महीने के आंकड़ों पर विश्लेषण।",
    accountantsNote:"📝 लेखाकार की टिप्पणी",narrativeRefresh:"नवीनीकरण",
    narrativePlaceholder:"नवीनीकरण दबाएं — मासिक विवरण तैयार होगा…",
    expenseBreakdown:"🖼 खर्च विवरण",noExpenseData:"अभी कोई खर्च डेटा नहीं।",
    chatQ1:"क़र्ज़दार कौन है?",chatQ2:"इस महीने लाभ?",chatQ3:"सबसे बड़ा खर्च?",chatQ4:"आपूर्तिकर्ता का कर्ज?",
    chatPlaceholder:"उदा. इस महीने चावल या दाल पर कितना खर्च हुआ?",
    chatAsk:"पूछें",
    reliabilityLabel:"विश्वसनीयता",priceStabilityLabel:"मूल्य स्थिरता",
    ordersLabel:"ऑर्डर",totalLabel:"कुल:",
    noPriorityActions:"कोई प्राथमिकता क्रिया नहीं — व्यवसाय स्वस्थ दिखता है!",
    noNegativeTrends:"कोई नकारात्मक रुझान नहीं मिला।",
    noPricingData:"अभी मूल्य अनुकूलन नहीं। इन्वेंटरी और बिक्री डेटा जोड़ें।",
    noDemandData:"अभी मांग डेटा नहीं।",
    noPurchaseData:"अभी खरीद अनुशंसा नहीं।",
    noSupplierData:"अभी आपूर्तिकर्ता इतिहास नहीं। खरीद दर्ज करें।",
    noPromoData:"अभी प्रमोशन अनुशंसा नहीं।",
    noBundleData:"अभी कोई बंडल सुझाव नहीं।",
    noLeakageData:"✅ कोई महत्वपूर्ण लाभ रिसाव नहीं मिला।",
    noRecoveryData:"अभी कुछ अत्यवश्यक नहीं।",
    copilotThinking:"सोच रहा हूँ…",copilotError:"कृपया पुनः प्रयास करें।",
    copilotModeWhatIf:"🔮 क्या-अगर सिमुलेशन",copilotModeRootCause:"🔍 मूल कारण विश्लेषण",copilotModeStandard:"💬 AI सहायक",
    // AI Intelligence
    aiIntelTitle:"AI निर्णय बुद्धिमत्ता",'''
content = content.replace(hi_old, hi_new)

# 3. Update Telugu translations
te_old = '''    recordUpdateBtn:"నమ౏దు చేయండి & స్టాక్ నవీకరించండి",addEditItem:"+ వస్తువు జోడించండి / సవరించండి",
    // AI Intelligence
    aiIntelTitle:"AI నిర్ణయ మేధస్సు",'''
te_new = '''    recordUpdateBtn:"నమ౏దు చేయండి & స్టాక్ నవీకరించండి",addEditItem:"+ వస్తువు జోడించండి / సవరించండి",
    narrativeSectionTitle:"📊 నెలవారీ వ్యాపార సారాంశం",
    narrativeSectionSub:"మీ AI అకౌంటెంట్ ఈ నెల అంకెలపై విశ్లేషణ.",
    accountantsNote:"📝 అకౌంటెంట్ నోట్",narrativeRefresh:"రిఫ్రెష్",
    narrativePlaceholder:"రిఫ్రెష్ నొక్కండి — నెలవారీ వివరణ తయారవుతుంది…",
    expenseBreakdown:"🖼 ఖర్చు వివరణ",noExpenseData:"ఇంకా ఖర్చు డేటా లేదు.",
    chatQ1:"ఎవరు అప్పు తీసుకోలేదు?",chatQ2:"ఈ నెల లాభం?",chatQ3:"అతిపెద్ద ఖర్చు?",chatQ4:"సరఫరాదారుకి అప్పు?",
    chatPlaceholder:"ఉదా. ఈ నెల బియ్యం లేదా పప్పుపుప్పులుపుప్పుప్పుని ఎంత ఖర్చు అయింది?",
    chatAsk:"అడగండి",
    reliabilityLabel:"విశ్వసనీయత",priceStabilityLabel:"ధర స్థిరత్వం",
    ordersLabel:"ఆర్డర్‌లు",totalLabel:"మొత్తం:",
    noPriorityActions:"ప్రాధాన్యత చర్యలు లేవు — వ్యాపారం ఆరోగ్యంగా ఉంది!",
    noNegativeTrends:"నకారాత్మక ప్రవణతలు కనుగొనలేదు.",
    noPricingData:"ఇంకా ధర అనుకూలనపు లేవు.",
    noDemandData:"ఇంకా డిమాండ్ డేటా లేదు.",
    noPurchaseData:"ఇంకా కొనుగోలు సిఫార్సులు లేవు.",
    noSupplierData:"ఇంకా సరఫరాదారు చరిత్ర లేదు.",
    noPromoData:"ఇంకా ప్రమోషన్ సిఫార్సులు లేవు.",
    noBundleData:"ఇంకా బండిల్ సూచనలు లేవు.",
    noLeakageData:"✅ మహత్వపూర్ణ నష్టం కనుగొనలేదు.",
    noRecoveryData:"ఇప్పుడు ఏమీ అత్యవసరం లేదు.",
    copilotThinking:"ఆలోచిస్తున్నాను…",copilotError:"దయచేసి మళ్ళీ ప్రయత్నించండి.",
    copilotModeWhatIf:"🔮 ఏమి జరుగుతుందా సిమ్యులేషన్",copilotModeRootCause:"🔍 మూల కారణ విశ్లేషణ",copilotModeStandard:"💬 AI సహాయకుడు",
    // AI Intelligence
    aiIntelTitle:"AI నిర్ణయ మేధస్సు",'''
content = content.replace(te_old, te_new)

# 4. Monthly narrative static elements
narr_old = '''    <section class="search-section" id="narrativeSection">
      <h2>📊 Monthly Business Summary</h2>
      <p class="sub">Your AI accountant's take on this month's numbers — in plain English, not spreadsheet jargon.</p>
      <div style="display:grid;grid-template-columns:3fr 2fr;gap:18px;align-items:start;">

        <!-- Narrative card -->
        <div class="connect-card" style="border-color:rgba(45,212,191,.2);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <h3 style="margin:0;">📝 Accountant's Note</h3>
            <button class="btn" onclick="loadNarrative()" style="padding:4px 12px;font-size:.78rem;">Refresh</button>
          </div>
          <div id="narrativeText" style="font-size:.9rem;line-height:1.75;color:var(--text-2);font-style:italic;">
            Click Refresh to generate your monthly narrative…
          </div>
        </div>

        <!-- Category pie chart -->
        <div class="connect-card" style="border-color:rgba(75,142,247,.2);">
          <h3>🗂️ Expense Breakdown</h3>
          <div id="categoryChart" style="min-height:160px;display:flex;flex-direction:column;gap:6px;">
            <div style="color:var(--text-3);font-size:.82rem;">No expense data yet.</div>
          </div>
        </div>
      </div>
    </section>'''

narr_new = '''    <section class="search-section" id="narrativeSection">
      <h2 id="narrativeSectionTitle">📊 Monthly Business Summary</h2>
      <p class="sub" id="narrativeSectionSub">Your AI accountant's take on this month's numbers — in plain language, not spreadsheet jargon.</p>
      <div style="display:grid;grid-template-columns:3fr 2fr;gap:18px;align-items:start;">

        <!-- Narrative card -->
        <div class="connect-card" style="border-color:rgba(45,212,191,.2);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <h3 id="accountantsNoteTitle" style="margin:0;">📝 Accountant's Note</h3>
            <button class="btn" id="narrativeRefreshBtn" onclick="loadNarrative()" style="padding:4px 12px;font-size:.78rem;">Refresh</button>
          </div>
          <div id="narrativeText" style="font-size:.9rem;line-height:1.75;color:var(--text-2);font-style:italic;">
            <span id="narrativePlaceholder">Click Refresh to generate your monthly narrative…</span>
          </div>
        </div>

        <!-- Category pie chart -->
        <div class="connect-card" style="border-color:rgba(75,142,247,.2);">
          <h3 id="expenseBreakdownTitle">🗂️ Expense Breakdown</h3>
          <div id="categoryChart" style="min-height:160px;display:flex;flex-direction:column;gap:6px;">
            <div id="noExpenseData" style="color:var(--text-3);font-size:.82rem;">No expense data yet.</div>
          </div>
        </div>
      </div>
    </section>'''
content = content.replace(narr_old, narr_new)

# 5. AI Chat static elements
chat_old = '''        <input id="chatQuestion" class="input-field" placeholder="e.g. Am I spending more on rice or dal this month?" style="flex:1;" onkeydown="if(event.key==='Enter')askLedgerChat()">
        <button class="btn" onclick="askLedgerChat()" id="chatBtn">Ask</button>
      </div>
      <div id="chatSuggestions" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
        <button class="app-btn" onclick="setQuestion('Who owes me the most money?')">Who owes me most?</button>
        <button class="app-btn" onclick="setQuestion('What is my net profit this month?')">Profit this month?</button>
        <button class="app-btn" onclick="setQuestion('Where am I spending the most?')">Biggest expenses?</button>
        <button class="app-btn" onclick="setQuestion('Which supplier do I owe the most?')">Supplier owed most?</button>
      </div>'''

chat_new = '''        <input id="chatQuestion" class="input-field" placeholder="e.g. Am I spending more on rice or dal this month?" style="flex:1;" onkeydown="if(event.key==='Enter')askLedgerChat()">
        <button class="btn" onclick="askLedgerChat()" id="chatAskBtn">Ask</button>
      </div>
      <div id="chatSuggestions" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
        <button id="chatQ1" class="app-btn" onclick="setQuestion(this.textContent)">Who owes me most?</button>
        <button id="chatQ2" class="app-btn" onclick="setQuestion(this.textContent)">Profit this month?</button>
        <button id="chatQ3" class="app-btn" onclick="setQuestion(this.textContent)">Biggest expenses?</button>
        <button id="chatQ4" class="app-btn" onclick="setQuestion(this.textContent)">Supplier owed most?</button>
      </div>'''
content = content.replace(chat_old, chat_new)

# 6. Apply string mappings
map_old = '''  // ── AI Chat section ─────────────────────────────────────
  setText("aiChatSectionTitle",    t.aiChatTitle);
  setHtml("aiChatSectionSub",      t.aiChatSub);
}'''
map_new = '''  // ── AI Chat section ─────────────────────────────────────
  setText("aiChatSectionTitle",    t.aiChatTitle);
  setHtml("aiChatSectionSub",      t.aiChatSub);

  // ── Monthly Narrative ──────────────────────────────────────
  setText("narrativeSectionTitle", t.narrativeSectionTitle);
  setText("narrativeSectionSub",   t.narrativeSectionSub);
  setText("accountantsNoteTitle",  t.accountantsNote);
  setText("narrativeRefreshBtn",   t.narrativeRefresh);
  setText("narrativePlaceholder",  t.narrativePlaceholder);
  setText("expenseBreakdownTitle", t.expenseBreakdown);
  setText("noExpenseData",         t.noExpenseData);

  // ── AI Chat chips ─────────────────────────────────────────
  setText("chatQ1", t.chatQ1);
  setText("chatQ2", t.chatQ2);
  setText("chatQ3", t.chatQ3);
  setText("chatQ4", t.chatQ4);
  setPlace("chatQuestion", t.chatPlaceholder);
  setText("chatAskBtn",  t.chatAsk);

  // ── Inventory input placeholders ────────────────────────────
  setPlace("manualQty",   t.quantity);
  setPlace("manualPrice", t.pricePerUnit);
  const manualItem = document.getElementById('manualItem');
  if (manualItem && manualItem.options[0]) manualItem.options[0].textContent = t.selectItem;
}'''
content = content.replace(map_old, map_new)

# 7. Render dynamic insights
render_health_old = '''// ── Render: Health Banner ──────────────────────────────────
function renderHealthBanner(copilot) {
  const banner = document.getElementById('copilotHealthBanner');
  if (!copilot.health_status) { banner.style.display = 'none'; return; }
  const icons   = { good: '✅', warning: '⚠️', critical: '🚨' };
  const titles  = { good: 'Business Health: Good', warning: 'Business Health: Needs Attention', critical: 'Business Health: Critical' };
  banner.className = `copilot-health health-${copilot.health_status}`;
  banner.innerHTML = `
    <div class="health-icon">${icons[copilot.health_status] || '📊'}</div>
    <div>
      <div class="health-title">${titles[copilot.health_status] || 'Business Status'}</div>
      <div class="health-label">${copilot.health_label || ''}</div>
    </div>`;
  banner.style.display = 'flex';
}'''

render_health_new = '''// ── Render: Health Banner ──────────────────────────────────
function renderHealthBanner(copilot) {
  const t = s();
  const banner = document.getElementById('copilotHealthBanner');
  if (!copilot.health_status) { banner.style.display = 'none'; return; }
  const icons   = { good: '✅', warning: '⚠️', critical: '🚨' };
  const titles  = { good: t.healthGood, warning: t.healthWarning, critical: t.healthCritical };
  banner.className = `copilot-health health-${copilot.health_status}`;
  banner.innerHTML = `
    <div class="health-icon">${icons[copilot.health_status] || '📊'}</div>
    <div>
      <div class="health-title">${titles[copilot.health_status] || copilot.health_status}</div>
      <div class="health-label">${copilot.health_label || ''}</div>
    </div>`;
  banner.style.display = 'flex';
}'''
content = content.replace(render_health_old, render_health_new)

render_actions_old = '''// ── Render: Priority Actions ───────────────────────────────
function renderPriorityActions(actions) {
  const el = document.getElementById('priorityActionsList');
  if (!actions.length) { el.innerHTML = '<div style="color:var(--text-3);font-size:.82rem;">No priority actions — your business looks healthy!</div>'; return; }'''
render_actions_new = '''// ── Render: Priority Actions ───────────────────────────────
function renderPriorityActions(actions) {
  const t = s();
  const el = document.getElementById('priorityActionsList');
  if (!actions.length) { el.innerHTML = `<div style="color:var(--text-3);font-size:.82rem;">${t.noPriorityActions}</div>`; return; }'''
content = content.replace(render_actions_old, render_actions_new)

render_root_old = '''// ── Render: Root Causes ────────────────────────────────────
function renderRootCauses(causes) {
  const el = document.getElementById('rootCausesList');
  if (!causes.length) { el.innerHTML = '<div style="color:var(--text-3);font-size:.82rem;">No negative trends detected.</div>'; return; }'''
render_root_new = '''// ── Render: Root Causes ────────────────────────────────────
function renderRootCauses(causes) {
  const t = s();
  const el = document.getElementById('rootCausesList');
  if (!causes.length) { el.innerHTML = `<div style="color:var(--text-3);font-size:.82rem;">${t.noNegativeTrends}</div>`; return; }'''
content = content.replace(render_root_old, render_root_new)

render_pricing_old = '''// ── Render: Pricing Optimizer ──────────────────────────────
function renderPricing(items) {
  const el = document.getElementById('pricingList');
  if (!items.length) { el.innerHTML = '<div style="color:var(--text-3);font-size:.82rem;">No pricing optimizations yet. Add inventory and sales data.</div>'; return; }
  el.innerHTML = items.map(item => {
    const badgeClass = 'badge-' + (item.badge || 'margin').toLowerCase().replace(/\s+/g, '-');
    return `
      <div class="price-row">
        <div class="price-item-name">${item.item_name || ''}</div>
        <span class="insight-badge ${badgeClass}">${item.badge || 'Margin Fix'}</span>
        <span class="price-from">₹${(item.current_cost||0).toLocaleString('en-IN')}</span>
        <span class="price-to">₹${(item.recommended_price||0).toLocaleString('en-IN')}</span>
        <button class="apply-price-btn" id="apply-${encodeURIComponent(item.item_name)}"
          onclick="applyPrice('${item.item_name.replace(/'/g,"\\'")}',${item.recommended_price})">Apply</button>
      </div>`;
  }).join('');
}'''
render_pricing_new = '''// ── Render: Pricing Optimizer ──────────────────────────────
function renderPricing(items) {
  const t = s();
  const el = document.getElementById('pricingList');
  if (!items.length) { el.innerHTML = `<div style="color:var(--text-3);font-size:.82rem;">${t.noPricingData}</div>`; return; }
  el.innerHTML = items.map(item => {
    const badgeClass = 'badge-' + (item.badge || 'margin').toLowerCase().replace(/\s+/g, '-');
    return `
      <div class="price-row">
        <div class="price-item-name">${item.item_name || ''}</div>
        <span class="insight-badge ${badgeClass}">${item.badge || 'Margin Fix'}</span>
        <span class="price-from">₹${(item.current_cost||0).toLocaleString('en-IN')}</span>
        <span class="price-to">₹${(item.recommended_price||0).toLocaleString('en-IN')}</span>
        <button class="apply-price-btn" id="apply-${encodeURIComponent(item.item_name)}"
          onclick="applyPrice('${item.item_name.replace(/'/g,"\\'")}',${item.recommended_price})">${t.applyLabel}</button>
      </div>`;
  }).join('');
}'''
content = content.replace(render_pricing_old, render_pricing_new)

apply_old = '''    if (res.ok) {
      btn.textContent = '✓ Applied';
      btn.classList.add('applied');
      loadInventory && loadInventory(); // refresh stock panel if function exists
    } else {'''
apply_new = '''    if (res.ok) {
      btn.textContent = s().appliedLabel;
      btn.classList.add('applied');
      loadInventory && loadInventory(); // refresh stock panel if function exists
    } else {'''
content = content.replace(apply_old, apply_new)

render_demand_old = '''// ── Render: Demand Forecast ────────────────────────────────
function renderDemand(items) {
  const el = document.getElementById('demandList');
  if (!items.length) { el.innerHTML = '<div style="color:var(--text-3);font-size:.82rem;">No demand data yet.</div>'; return; }
  el.innerHTML = items.map(item => {
    const urgency  = (item.reorder_urgency || 'low').toLowerCase();
    const barW     = urgency === 'high' ? 90 : urgency === 'medium' ? 55 : 20;
    const days     = item.days_of_stock >= 999 ? '∞' : item.days_of_stock;
    return `
      <div class="demand-row">
        <div class="demand-header">
          <span class="demand-name">${item.item_name || ''}</span>
          <span class="insight-badge badge-${urgency}">${urgency} urgency</span>
        </div>
        <div style="font-size:.73rem;color:var(--text-3);margin-bottom:4px;">
          Stock: ${(item.current_stock||0)} ${item.unit||'units'} · ~${days} days left · Reorder: ${item.recommended_reorder_qty||'?'} ${item.unit||''}
        </div>
        <div class="demand-bar-wrap">
          <div class="demand-bar bar-${urgency}" style="width:${barW}%;"></div>
        </div>
      </div>`;
  }).join('');
}'''
render_demand_new = '''// ── Render: Demand Forecast ────────────────────────────────
function renderDemand(items) {
  const t = s();
  const el = document.getElementById('demandList');
  if (!items.length) { el.innerHTML = `<div style="color:var(--text-3);font-size:.82rem;">${t.noDemandData}</div>`; return; }
  const urgencyMap = { high: t.highUrgency, medium: t.mediumUrgency, low: t.lowUrgency };
  el.innerHTML = items.map(item => {
    const urgency  = (item.reorder_urgency || 'low').toLowerCase();
    const barW     = urgency === 'high' ? 90 : urgency === 'medium' ? 55 : 20;
    const days     = item.days_of_stock >= 999 ? '∞' : item.days_of_stock;
    return `
      <div class="demand-row">
        <div class="demand-header">
          <span class="demand-name">${item.item_name || ''}</span>
          <span class="insight-badge badge-${urgency}">${urgencyMap[urgency] || urgency}</span>
        </div>
        <div style="font-size:.73rem;color:var(--text-3);margin-bottom:4px;">
          ${t.stockLabel} ${(item.current_stock||0)} ${item.unit||''} · ~${days} ${t.daysLeft} · ${t.reorderLabel} ${item.recommended_reorder_qty||'?'} ${item.unit||''}
        </div>
        <div class="demand-bar-wrap">
          <div class="demand-bar bar-${urgency}" style="width:${barW}%;"></div>
        </div>
      </div>`;
  }).join('');
}'''
content = content.replace(render_demand_old, render_demand_new)

render_purchase_old = '''// ── Render: Purchase Optimizer ─────────────────────────────
function renderPurchase(recs) {
  const el = document.getElementById('purchaseList');
  if (!recs.length) { el.innerHTML = '<div style="color:var(--text-3);font-size:.82rem;">No purchase recommendations yet.</div>'; return; }
  el.innerHTML = recs.map(rec => {
    const itemsHtml = (rec.items || []).map(i =>
      `<div style="display:flex;justify-content:space-between;font-size:.78rem;color:var(--text-2);padding:3px 0;">
        <span>${i.name} — ${i.qty} ${i.unit||''}</span>
        <span style="color:var(--teal);">₹${(i.estimated_cost||0).toLocaleString('en-IN')}</span>
       </div>`).join('');
    return `
      <div style="background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius);padding:14px;margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <div style="font-size:.85rem;font-weight:700;color:var(--text);">🏪 ${rec.supplier_name || 'Supplier'}</div>
          <div style="font-size:.82rem;font-weight:700;color:var(--amber);">₹${(rec.total_estimated_cost||0).toLocaleString('en-IN')}</div>
        </div>
        ${itemsHtml}
        <div style="margin-top:8px;font-size:.72rem;color:var(--text-3);">Coverage: ~${rec.coverage_days||'?'} days · ${rec.rationale||''}</div>
      </div>`;
  }).join('');
}'''
render_purchase_new = '''// ── Render: Purchase Optimizer ─────────────────────────────
function renderPurchase(recs) {
  const t = s();
  const el = document.getElementById('purchaseList');
  if (!recs.length) { el.innerHTML = `<div style="color:var(--text-3);font-size:.82rem;">${t.noPurchaseData}</div>`; return; }
  el.innerHTML = recs.map(rec => {
    const itemsHtml = (rec.items || []).map(i =>
      `<div style="display:flex;justify-content:space-between;font-size:.78rem;color:var(--text-2);padding:3px 0;">
        <span>${i.name} — ${i.qty} ${i.unit||''}</span>
        <span style="color:var(--teal);">₹${(i.estimated_cost||0).toLocaleString('en-IN')}</span>
       </div>`).join('');
    return `
      <div style="background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius);padding:14px;margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <div style="font-size:.85rem;font-weight:700;color:var(--text);">🏪 ${rec.supplier_name || 'Supplier'}</div>
          <div style="font-size:.82rem;font-weight:700;color:var(--amber);">₹${(rec.total_estimated_cost||0).toLocaleString('en-IN')}</div>
        </div>
        ${itemsHtml}
        <div style="margin-top:8px;font-size:.72rem;color:var(--text-3);">${t.coverageLabel} ~${rec.coverage_days||'?'} ${t.days} · ${rec.rationale||''}</div>
      </div>`;
  }).join('');
}'''
content = content.replace(render_purchase_old, render_purchase_new)

render_supplier_old = '''// ── Render: Supplier Intelligence ─────────────────────────
function renderSuppliers(suppliers) {
  const el = document.getElementById('supplierList');
  if (!suppliers.length) { el.innerHTML = '<div style="color:var(--text-3);font-size:.82rem;">No supplier history yet. Record purchases to see scores.</div>'; return; }
  const trendIcon = { stable: '→', rising: '↑', falling: '↓' };
  const recColor  = { continue: 'var(--teal)', watch: 'var(--amber)', replace: 'var(--red)' };
  el.innerHTML = suppliers.map(s => `
    <div class="supplier-card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div class="supplier-name">${s.supplier_name||'Unknown'}</div>
        <div style="font-size:.72rem;font-weight:700;color:${recColor[s.recommendation]||'var(--teal)'};">
          ${(s.recommendation||'continue').toUpperCase()} ${trendIcon[s.trend]||''}
        </div>
      </div>
      <div class="score-row">
        <span class="score-label">Reliability</span>
        <div class="score-bar-wrap"><div class="score-bar" style="width:${s.reliability_score||0}%;"></div></div>
        <span class="score-val">${s.reliability_score||0}%</span>
      </div>
      <div class="score-row">
        <span class="score-label">Price Stability</span>
        <div class="score-bar-wrap"><div class="score-bar" style="width:${s.price_stability_score||0}%;"></div></div>
        <span class="score-val">${s.price_stability_score||0}%</span>
      </div>
      <div style="font-size:.72rem;color:var(--text-3);margin-top:6px;">
        ${s.order_count||0} orders · Total: ₹${(s.total_spent||0).toLocaleString('en-IN')}
      </div>
    </div>`).join('');
}'''
render_supplier_new = '''// ── Render: Supplier Intelligence ─────────────────────────
function renderSuppliers(suppliers) {
  const t = s();
  const el = document.getElementById('supplierList');
  if (!suppliers.length) { el.innerHTML = `<div style="color:var(--text-3);font-size:.82rem;">${t.noSupplierData}</div>`; return; }
  const trendIcon = { stable: '→', rising: '↑', falling: '↓' };
  const recColor  = { continue: 'var(--teal)', watch: 'var(--amber)', replace: 'var(--red)' };
  el.innerHTML = suppliers.map(s2 => `
    <div class="supplier-card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div class="supplier-name">${s2.supplier_name||'Unknown'}</div>
        <div style="font-size:.72rem;font-weight:700;color:${recColor[s2.recommendation]||'var(--teal)'};">
          ${(s2.recommendation||'continue').toUpperCase()} ${trendIcon[s2.trend]||''}
        </div>
      </div>
      <div class="score-row">
        <span class="score-label">${t.reliabilityLabel}</span>
        <div class="score-bar-wrap"><div class="score-bar" style="width:${s2.reliability_score||0}%;"></div></div>
        <span class="score-val">${s2.reliability_score||0}%</span>
      </div>
      <div class="score-row">
        <span class="score-label">${t.priceStabilityLabel}</span>
        <div class="score-bar-wrap"><div class="score-bar" style="width:${s2.price_stability_score||0}%;"></div></div>
        <span class="score-val">${s2.price_stability_score||0}%</span>
      </div>
      <div style="font-size:.72rem;color:var(--text-3);margin-top:6px;">
        ${s2.order_count||0} ${t.ordersLabel} · ${t.totalLabel} ₹${(s2.total_spent||0).toLocaleString('en-IN')}
      </div>
    </div>`).join('');
}'''
content = content.replace(render_supplier_old, render_supplier_new)

render_promotions_old = '''// ── Render: Promotions ─────────────────────────────────────
function renderPromotions(promos) {
  const el = document.getElementById('promotionList');
  if (!promos.length) { el.innerHTML = '<div style="color:var(--text-3);font-size:.82rem;">No promotion recommendations yet.</div>'; return; }
  const typeClass = {
    'Weekend Discount': 'badge-weekend', 'Festival Offer': 'badge-festival',
    'Clearance Sale': 'badge-clearance', 'Combo Pack': 'badge-combo', 'BOGO': 'badge-bogo'
  };
  el.innerHTML = promos.map(p => `
    <div class="insight-card" style="margin-bottom:10px;">
      <div class="insight-card-header">
        <span class="insight-card-title">${p.title||''}</span>
        <span class="insight-badge ${typeClass[p.type]||'badge-combo'}">${p.type||'Offer'}</span>
      </div>
      <div class="insight-desc">${p.description||''}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <div class="insight-metric">+${p.expected_lift_pct||0}%</div>
          <div class="insight-metric-label">Expected Lift</div>
        </div>
        <div style="font-size:.72rem;color:var(--text-3);">📅 ${p.urgency||''}</div>
      </div>
    </div>`).join('');
}'''
render_promotions_new = '''// ── Render: Promotions ─────────────────────────────────────
function renderPromotions(promos) {
  const t = s();
  const el = document.getElementById('promotionList');
  if (!promos.length) { el.innerHTML = `<div style="color:var(--text-3);font-size:.82rem;">${t.noPromoData}</div>`; return; }
  const typeClass = {
    'Weekend Discount': 'badge-weekend', 'Festival Offer': 'badge-festival',
    'Clearance Sale': 'badge-clearance', 'Combo Pack': 'badge-combo', 'BOGO': 'badge-bogo'
  };
  el.innerHTML = promos.map(p => `
    <div class="insight-card" style="margin-bottom:10px;">
      <div class="insight-card-header">
        <span class="insight-card-title">${p.title||''}</span>
        <span class="insight-badge ${typeClass[p.type]||'badge-combo'}">${p.type||'Offer'}</span>
      </div>
      <div class="insight-desc">${p.description||''}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <div class="insight-metric">+${p.expected_lift_pct||0}%</div>
          <div class="insight-metric-label">${t.expectedLift}</div>
        </div>
        <div style="font-size:.72rem;color:var(--text-3);">📅 ${p.urgency||''}</div>
      </div>
    </div>`).join('');
}'''
content = content.replace(render_promotions_old, render_promotions_new)

render_bundles_old = '''// ── Render: Smart Bundles ──────────────────────────────────
function renderBundles(bundles) {
  const el = document.getElementById('bundleList');
  if (!bundles.length) { el.innerHTML = '<div style="color:var(--text-3);font-size:.82rem;">No bundle suggestions yet.</div>'; return; }
  el.innerHTML = bundles.map(b => `
    <div style="background:var(--surface-2);border:1px solid rgba(45,212,191,.15);border-radius:var(--radius);padding:14px;margin-bottom:10px;">
      <div style="font-size:.88rem;font-weight:700;color:var(--text);margin-bottom:6px;">🛍 ${b.bundle_name||'Bundle'}</div>
      <div class="bundle-products">
        ${(b.products||[]).map(p => `<span class="bundle-tag">${p}</span>`).join('')}
      </div>
      <div style="font-size:.78rem;color:var(--text-2);margin-bottom:6px;">${b.rationale||''}</div>
      <div style="display:flex;gap:16px;">
        <div><span class="insight-metric" style="font-size:.95rem;">${b.discount_pct||0}%</span><span class="insight-metric-label" style="margin-left:4px;">Discount</span></div>
        <div><span class="insight-metric" style="font-size:.95rem;">+${b.basket_value_lift_pct||0}%</span><span class="insight-metric-label" style="margin-left:4px;">Basket Lift</span></div>
      </div>
    </div>`).join('');
}'''
render_bundles_new = '''// ── Render: Smart Bundles ──────────────────────────────────
function renderBundles(bundles) {
  const t = s();
  const el = document.getElementById('bundleList');
  if (!bundles.length) { el.innerHTML = `<div style="color:var(--text-3);font-size:.82rem;">${t.noBundleData}</div>`; return; }
  el.innerHTML = bundles.map(b => `
    <div style="background:var(--surface-2);border:1px solid rgba(45,212,191,.15);border-radius:var(--radius);padding:14px;margin-bottom:10px;">
      <div style="font-size:.88rem;font-weight:700;color:var(--text);margin-bottom:6px;">🛍 ${b.bundle_name||'Bundle'}</div>
      <div class="bundle-products">
        ${(b.products||[]).map(p => `<span class="bundle-tag">${p}</span>`).join('')}
      </div>
      <div style="font-size:.78rem;color:var(--text-2);margin-bottom:6px;">${b.rationale||''}</div>
      <div style="display:flex;gap:16px;">
        <div><span class="insight-metric" style="font-size:.95rem;">${b.discount_pct||0}%</span><span class="insight-metric-label" style="margin-left:4px;">${t.discountLabel}</span></div>
        <div><span class="insight-metric" style="font-size:.95rem;">+${b.basket_value_lift_pct||0}%</span><span class="insight-metric-label" style="margin-left:4px;">${t.basketLift}</span></div>
      </div>
    </div>`).join('');
}'''
content = content.replace(render_bundles_old, render_bundles_new)

render_leakage_old = '''// ── Render: Profit Leakage ─────────────────────────────────
function renderLeakage(leakage) {
  const totalEl    = document.getElementById('leakageTotal');
  const listEl     = document.getElementById('leakageList');
  const actionsEl  = document.getElementById('recoveryActionsList');
  const total      = leakage.total_estimated_loss || 0;
  const breakdown  = leakage.breakdown || [];

  // Total card
  if (total > 0) {
    totalEl.innerHTML = `
      <div class="leakage-amount">₹${total.toLocaleString('en-IN')}</div>
      <div class="leakage-label">Estimated Monthly Profit Leakage</div>`;
    totalEl.style.display = 'block';
  } else {
    totalEl.style.display = 'none';
  }

  // Breakdown rows
  const catIcons = {
    'Dead Stock': '📦', 'Expired Products': '⚠️',
    'Supplier Overpricing': '💸', 'Excess Discounts': '🏷️', 'Slow Movers': '🐌'
  };
  if (!breakdown.length) {
    listEl.innerHTML = '<div style="color:var(--teal);font-size:.85rem;padding:12px 0;">✅ No significant leakage detected. Business looks tight!</div>';
  } else {
    listEl.innerHTML = breakdown.map(b => `
      <div class="leakage-row">
        <div class="leakage-icon">${catIcons[b.category]||'📊'}</div>
        <div class="leakage-info">
          <div class="leakage-cat">${b.category||''}</div>
          <div class="leakage-desc">${b.description||''}</div>
          <div class="leakage-action">→ ${b.action||''}</div>
        </div>
        <div class="leakage-val">₹${(b.estimated_loss||0).toLocaleString('en-IN')}</div>
      </div>`).join('');
  }

  // Recovery actions (just re-use breakdown actions as a clean list)
  if (!breakdown.length) {
    actionsEl.innerHTML = '<div style="color:var(--teal);font-size:.82rem;">Nothing urgent right now.</div>';
  } else {'''
render_leakage_new = '''// ── Render: Profit Leakage ─────────────────────────────────
function renderLeakage(leakage) {
  const t = s();
  const totalEl    = document.getElementById('leakageTotal');
  const listEl     = document.getElementById('leakageList');
  const actionsEl  = document.getElementById('recoveryActionsList');
  const total      = leakage.total_estimated_loss || 0;
  const breakdown  = leakage.breakdown || [];

  // Total card
  if (total > 0) {
    totalEl.innerHTML = `
      <div class="leakage-amount">₹${total.toLocaleString('en-IN')}</div>
      <div class="leakage-label">${t.estimatedLeakage}</div>`;
    totalEl.style.display = 'block';
  } else {
    totalEl.style.display = 'none';
  }

  // Breakdown rows
  const catIcons = {
    'Dead Stock': '📦', 'Expired Products': '⚠️',
    'Supplier Overpricing': '💸', 'Excess Discounts': '🏷️', 'Slow Movers': '🐌'
  };
  if (!breakdown.length) {
    listEl.innerHTML = `<div style="color:var(--teal);font-size:.85rem;padding:12px 0;">${t.noLeakageData}</div>`;
  } else {
    listEl.innerHTML = breakdown.map(b => `
      <div class="leakage-row">
        <div class="leakage-icon">${catIcons[b.category]||'📊'}</div>
        <div class="leakage-info">
          <div class="leakage-cat">${b.category||''}</div>
          <div class="leakage-desc">${b.description||''}</div>
          <div class="leakage-action">→ ${b.action||''}</div>
        </div>
        <div class="leakage-val">₹${(b.estimated_loss||0).toLocaleString('en-IN')}</div>
      </div>`).join('');
  }

  // Recovery actions (just re-use breakdown actions as a clean list)
  if (!breakdown.length) {
    actionsEl.innerHTML = `<div style="color:var(--teal);font-size:.82rem;">${t.noRecoveryData}</div>`;
  } else {'''
content = content.replace(render_leakage_old, render_leakage_new)

ask_copilot_old = '''async function askCopilot() {
  const input = document.getElementById('copilotInput');
  const ansEl = document.getElementById('copilotAnswer');
  const sendBtn = document.getElementById('copilotSendBtn');
  const q = (input.value||'').trim();
  if (!q) return;

  sendBtn.textContent = '…';
  sendBtn.disabled    = true;
  ansEl.style.display  = 'block';
  ansEl.innerHTML      = '<span style="color:var(--text-3);">Thinking…</span>';

  try {
    const res  = await fetch('/api/chat/ledger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });
    const data = await res.json();
    const modeLabel = data.mode === 'what_if' ? '🔮 What-If Simulation' :
                      data.mode === 'root_cause' ? '🔍 Root Cause Analysis' : '💬 AI Copilot';
    ansEl.innerHTML = `
      <div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--teal);margin-bottom:6px;">${modeLabel}</div>
      <div>${(data.answer||'').replace(/\\n/g,'<br>')}</div>`;
  } catch(e) {
    ansEl.innerHTML = '<span style="color:var(--red);">Error contacting AI. Please try again.</span>';
  } finally {
    sendBtn.textContent = 'Ask';
    sendBtn.disabled    = false;
  }
}'''
ask_copilot_new = '''async function askCopilot() {
  const t = s();
  const input = document.getElementById('copilotInput');
  const ansEl = document.getElementById('copilotAnswer');
  const sendBtn = document.getElementById('copilotSendBtn');
  const q = (input.value||'').trim();
  if (!q) return;

  sendBtn.textContent = '…';
  sendBtn.disabled    = true;
  ansEl.style.display  = 'block';
  ansEl.innerHTML      = `<span style="color:var(--text-3);">${t.copilotThinking}</span>`;

  try {
    const res  = await fetch('/api/chat/ledger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, language: currentLang })
    });
    const data = await res.json();
    const modeLabel = data.mode === 'what_if' ? t.copilotModeWhatIf :
                      data.mode === 'root_cause' ? t.copilotModeRootCause : t.copilotModeStandard;
    ansEl.innerHTML = `
      <div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--teal);margin-bottom:6px;">${modeLabel}</div>
      <div>${(data.answer||'').replace(/\\n/g,'<br>')}</div>`;
  } catch(e) {
    ansEl.innerHTML = `<span style="color:var(--red);">${t.copilotError}</span>`;
  } finally {
    sendBtn.textContent = t.askBtn;
    sendBtn.disabled    = false;
  }
}'''
content = content.replace(ask_copilot_old, ask_copilot_new)

load_narrative_old = '''async function loadNarrative() {
  const el = document.getElementById('narrativeText');
  if (!el) return;
  el.innerHTML = '<span style="color:var(--text-3);font-style:italic;">Generating accountant\\'s note…</span>';
  try {
    const r   = await fetch('/api/dashboard/narrative');
    const d   = await r.json();
    el.style.fontStyle = 'normal';
    el.innerHTML = d.narrative ? d.narrative.replace(/\\n/g,'<br>') : 'No data for this period.';
  } catch(e) {
    el.textContent = 'Failed to generate narrative. Please try again.';
  }
}'''
load_narrative_new = '''async function loadNarrative() {
  const t  = s();
  const el = document.getElementById('narrativeText');
  if (!el) return;
  el.innerHTML = `<span style="color:var(--text-3);font-style:italic;">${currentLang === 'hindi' ? 'विवरण तैयार हो रहा है…' : currentLang === 'telugu' ? 'వివరణ తయారవుతోంది…' : 'Generating narrative…'}</span>`;
  try {
    const r   = await fetch(`/api/dashboard/narrative?language=${currentLang}`);
    const d   = await r.json();
    el.style.fontStyle = 'normal';
    el.innerHTML = d.narrative ? d.narrative.replace(/\\n/g,'<br>') : t.noExpenseData;
  } catch(e) {
    el.textContent = t.copilotError;
  }
}'''
content = content.replace(load_narrative_old, load_narrative_new)

load_insights_old = '''  try {
    const res  = await fetch('/api/dashboard/insights');
    const data = await res.json();'''
load_insights_new = '''  try {
    const res  = await fetch(`/api/dashboard/insights?language=${currentLang}`);
    const data = await res.json();'''
content = content.replace(load_insights_old, load_insights_new)

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Success')
