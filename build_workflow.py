import json
import uuid

# ── Node IDs (stable, reused from n8n) ──
node_ids = {
    "Webhook1": "65f757d5-7045-45df-90aa-a959a4a10519",
    "Respond OK1": "c370ae94-67de-411e-8368-4d479f00e421",
    "fromMe Check": "5527d4b8-019e-4bb6-bbd3-526fab1f9470",
    "Batch Collector": "cf3dc39b-5fa7-5389-ac72-94e2862a9cc2",
    "Should Process?": "6d6eba4b-4ded-5387-8f29-7d518c86632f",
    "Is Command?": "cc-001-cmd-check",
    "Store Context": "d7ae6ef8-a8e2-5779-a8fb-7a98a18f48c3",
    "AI Agent": "9409b931-1973-4c94-9d6e-5c255f6ee037",
    "OpenAI Chat Model1": "1b7c08e5-1da2-4a07-b017-370d41c50e85",
    "Simple Memory": "8627d7e8-8bc2-4449-b79b-dd1a4c04c32d",
    "Parse AI Output": "64249ad4-6e81-5542-bfda-6929c6c28aa6",
    "Clear Batch": "77f0e3d1-9d66-5d9b-a5b4-d30379bc9dd1",
    "Should Notify Admins?": "cond-notify-admins-node",
    "Should Reply Customer?": "cond-reply-customer-node",
    "Phone A Send": "61d75176-a426-41d9-8a8e-6d4c626f8df5",
    "Phone B Send": "e43d47e9-69fe-4bbd-9e59-59ccd0a31629",
    "Reply to Customer": "ad29ccfa-691f-584b-8212-198b25bbbc24",
    "Schedule Trigger": "0a90afa9-6731-5ce6-a4d0-76a4fc92898f",
    "Stale Batch Check": "7fa1b04c-9639-5b87-99e7-e21c1d1bfc3b",
    "Stale Exists?": "0304e900-4c6f-5cb7-a857-3c5f2e302d90",
    "Idle Timeout Check": "idle-check-001",
    "Idle Alert?": "idle-check-if-001",
}


def get_node_id(name):
    return node_ids.get(name, str(uuid.uuid5(uuid.NAMESPACE_DNS, f"n8n.workflow.filtreoto.{name}")))


# ── JS Code Blocks ──

batch_collector_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const input = $input.first().json;\n\n"
    "const rawJid = input.body.data.key.remoteJid || '';\n"
    "const senderNumber = rawJid.replace('@s.whatsapp.net', '').replace('@g.us', '');\n"
    "const senderName = input.body.data.pushName || senderNumber;\n"
    "const messageText = (input.body.data.message?.conversation\n"
    "  || input.body.data.message?.extendedTextMessage?.text\n"
    "  || input.body.data.message?.imageMessage?.caption\n"
    "  || '[Medya]').trim();\n\n"
    "const messageId = String(input.body.data.key.id || '');\n"
    "const fromMe = input.body.data.key.fromMe === true;\n"
    "const now = Date.now();\n"
    "const maxMessages = 30;\n\n"
    "if (!staticData._batches) staticData._batches = {};\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n"
    "if (!staticData._seenMessageIds) staticData._seenMessageIds = {};\n\n"
    "// Deduplication Check\n"
    "if (messageId && staticData._seenMessageIds[messageId]) {\n"
    "  return [{ json: { _action: 'ignore', reason: 'duplicate_message', messageId } }];\n"
    "}\n"
    "if (messageId) {\n"
    "  staticData._seenMessageIds[messageId] = now;\n"
    "  const ids = Object.keys(staticData._seenMessageIds);\n"
    "  if (ids.length > 3000) {\n"
    "    ids.sort((a, b) => staticData._seenMessageIds[a] - staticData._seenMessageIds[b])\n"
    "       .slice(0, ids.length - 2500)\n"
    "       .forEach(id => delete staticData._seenMessageIds[id]);\n"
    "  }\n"
    "}\n\n"
    "// === ++/-- KOMUTLARI: HER ZAMAN KOMUT OLARAK ISLE ===\n"
    "if (messageText === '++') {\n"
    "  staticData._manualModes[senderNumber] = true;\n"
    "  delete staticData._batches[senderNumber];\n"
    "  return [{ json: {\n"
    "    _action: 'command',\n"
    "    senderNumber: senderNumber,\n"
    "    command: 'paused',\n"
    "    bildirim: 'Sistem Manuel De - ' + senderName + ' (' + senderNumber + ')'\n"
    "  }}];\n"
    "}\n\n"
    "if (messageText === '--') {\n"
    "  staticData._manualModes[senderNumber] = false;\n"
    "  return [{ json: {\n"
    "    _action: 'command',\n"
    "    senderNumber: senderNumber,\n"
    "    command: 'resumed',\n"
    "    bildirim: 'Sistem Otomatik - ' + senderName + ' (' + senderNumber + ')'\n"
    "  }}];\n"
    "}\n\n"
    "if (fromMe || staticData._manualModes[senderNumber] === true) {\n"
    "  return [{ json: { _action: 'ignore' } }];\n"
    "}\n\n"
    "// === BATCH TOPLAMA (State Isolation ile) ===\n"
    "if (!staticData._batches[senderNumber]) {\n"
    "  staticData._batches[senderNumber] = {\n"
    "    pendingMessages: [],\n"
    "    processingMessages: [],\n"
    "    pendingStartedAt: now,\n"
    "    lastMessageAt: now,\n"
    "    processingStartedAt: null,\n"
    "    processingToken: null,\n"
    "    senderName: senderName,\n"
    "    processing: false,\n"
    "    hasImages: false\n"
    "  };\n"
    "}\n\n"
    "const batch = staticData._batches[senderNumber];\n"
    "if (!Array.isArray(batch.pendingMessages)) batch.pendingMessages = [];\n"
    "if (!Array.isArray(batch.processingMessages)) batch.processingMessages = [];\n\n"
    "if (batch.pendingMessages.length >= maxMessages) {\n"
    "  return [{ json: { _action: 'spam_limit', senderNumber, senderName } }];\n"
    "}\n\n"
    "const hasImage = input.body.data.message?.imageMessage ? true : false;\n"
    "if (hasImage) batch.hasImages = true;\n\n"
    "if (!batch.pendingStartedAt || batch.pendingMessages.length === 0) {\n"
    "  batch.pendingStartedAt = now;\n"
    "}\n\n"
    "batch.pendingMessages.push({\n"
    "  id: messageId,\n"
    "  text: messageText,\n"
    "  type: hasImage ? 'image' : 'text',\n"
    "  timestamp: now,\n"
    "  time: new Date(now).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }),\n"
    "  mediaUrl: input.body.data.message?.imageMessage?.url || null,\n"
    "  mediaKey: input.body.data.message?.imageMessage?.mediaKey || null,\n"
    "  mimetype: input.body.data.message?.imageMessage?.mimetype || null\n"
    "});\n\n"
    "batch.lastMessageAt = now;\n"
    "batch.senderName = senderName;\n\n"
    "return [{ json: {\n"
    "  _action: batch.processing ? 'queued_during_processing' : 'queued',\n"
    "  senderNumber,\n"
    "  senderName,\n"
    "  pendingCount: batch.pendingMessages.length,\n"
    "  processing: batch.processing === true\n"
    "}}];"
)

stale_batch_check_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const now = Date.now();\n\n"
    "const IDLE_WINDOW_MS     = 35 * 1000;      // 35 sn sessizlik -> hemen işle\n"
    "const MAX_WAIT_MS        = 60 * 1000;      // 60 sn toplam max bekleme\n"
    "const PROCESSING_TIMEOUT = 2 * 60 * 1000;  // 2 dk AI işlem timeout recovery\n\n"
    "if (!staticData._batches) staticData._batches = {};\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n\n"
    "const ready = [];\n\n"
    "for (const [number, rawBatch] of Object.entries(staticData._batches)) {\n"
    "  const batch = rawBatch || {};\n"
    "  if (!Array.isArray(batch.pendingMessages)) batch.pendingMessages = Array.isArray(batch.messages) ? batch.messages : [];\n"
    "  if (!Array.isArray(batch.processingMessages)) batch.processingMessages = [];\n"
    "  delete batch.messages;\n\n"
    "  if (staticData._manualModes[number] === true) {\n"
    "    delete staticData._batches[number];\n"
    "    continue;\n"
    "  }\n\n"
    "  // Yarım kalan AI işlemini yeniden kuyruğa al\n"
    "  if (batch.processing === true && batch.processingStartedAt && (now - Number(batch.processingStartedAt) > PROCESSING_TIMEOUT)) {\n"
    "    batch.pendingMessages = [...batch.processingMessages, ...batch.pendingMessages];\n"
    "    batch.processingMessages = [];\n"
    "    batch.processing = false;\n"
    "    batch.processingStartedAt = null;\n"
    "    batch.processingToken = null;\n"
    "  }\n\n"
    "  if (batch.processing === true) continue;\n"
    "  if (!batch.pendingMessages.length) {\n"
    "    delete staticData._batches[number];\n"
    "    continue;\n"
    "  }\n\n"
    "  const lastTime  = Number(batch.lastMessageAt || batch.lastMessageTime || now);\n"
    "  const startTime = Number(batch.pendingStartedAt || batch.startTime || now);\n"
    "  const idleTime  = now - lastTime;\n"
    "  const totalTime = now - startTime;\n\n"
    "  const isIdleReady      = idleTime >= IDLE_WINDOW_MS;\n"
    "  const isMaxTimeReached = totalTime >= MAX_WAIT_MS;\n\n"
    "  if (isIdleReady || isMaxTimeReached) {\n"
    "    ready.push({ number, lastTime, batch, triggeredBy: isIdleReady ? 'idle' : 'max_time' });\n"
    "  }\n"
    "}\n\n"
    "ready.sort((a, b) => a.lastTime - b.lastTime);\n"
    "const selected = ready[0];\n\n"
    "if (!selected) {\n"
    "  return [{ json: { senderNumber: '', messageCount: 0, _ready: false } }];\n"
    "}\n\n"
    "const { number, batch } = selected;\n"
    "const processingMessages = batch.pendingMessages.splice(0);\n"
    "const processingToken = number + '-' + now + '-' + Math.random().toString(36).slice(2, 10);\n\n"
    "batch.processingMessages = processingMessages;\n"
    "batch.processing = true;\n"
    "batch.processingStartedAt = now;\n"
    "batch.processingToken = processingToken;\n"
    "batch.pendingStartedAt = null; // Sıfırla ki işlemdeyken gelen mesajlar yeni sayaç başlatsın\n\n"
    "const allMessagesText = processingMessages\n"
    "  .map((message, index) => `${index + 1}. [${message.time || ''}] ${message.text}`)\n"
    "  .join('\\n');\n\n"
    "const hasImages = processingMessages.some(m => m.type === 'image');\n"
    "const imageMessages = processingMessages\n"
    "  .filter(m => m.type === 'image' && m.mediaUrl)\n"
    "  .map(m => ({ mediaUrl: m.mediaUrl, mediaKey: m.mediaKey, mimetype: m.mimetype }));\n\n"
    "return [{\n"
    "  json: {\n"
    "    _ready: true,\n"
    "    senderNumber: number,\n"
    "    senderName: batch.senderName || number,\n"
    "    messageCount: processingMessages.length,\n"
    "    allMessagesText,\n"
    "    batchToken: processingToken,\n"
    "    hasImages,\n"
    "    imageMessages\n"
    "  }\n"
    "}];"
)

store_context_js = (
    "const input = $input.first().json;\n\n"
    "const allMessages  = String(input.allMessagesText || '');\n"
    "const messageCount = Number(input.messageCount || 0);\n"
    "const senderName   = String(input.senderName || '');\n\n"
    "// FİLTRE KODU PATTERN TARAMASI\n"
    "const codePatterns = [\n"
    "  /\\b(?:MANN[-\\s]?)?(?:W|C|HU|WK|PU|PL)\\s?\\d{2,4}(?:\\s?[\\/\\-]\\s?\\d{1,2})?(?:\\s?[xX])?\\b/gi,\n"
    "  /\\b(?:FILTRON[-\\s]?)?(?:OP|P|OS|OW|PS|WS|AS|AP|L|LS)\\s?\\d{3,4}(?:\\s?[\\/\\-]\\s?\\d{1,2})?\\b/gi,\n"
    "  /\\b(?:UFI[-\\s]?)?\\d{2}\\.\\d{2}\\.\\d{2}(?:[\\/\\-]\\d)?\\b/gi,\n"
    "  /\\b(?:HENGST[-\\s]?)?E\\s?\\d{1,2}[A-Z]\\s?D?\\s?\\d{2,3}[A-Z]?\\b/gi,\n"
    "  /\\b(?:PURFLUX[-\\s]?)?LS\\s?\\d{3,4}(?:[\\/\\-]\\d{1,2})?\\b/gi,\n"
    "  /\\b(?:MAHLE[-\\s]?)?(?:OX|OC|KC|KL|KX|PI|LS|W)\\s?\\d{2,4}[A-Z]?\\b/gi,\n"
    "  /\\b(?:FILTORQ[-\\s]?)?[A-Z]{1,3}\\s?\\d{3,4}(?:[\\/\\-]\\d{1,2})?\\b/gi,\n"
    "  /\\b\\d{3,4}\\s?[\\/\\-]\\s?\\d{1,2}\\b/g\n"
    "];\n\n"
    "const detectedCodes = [];\n"
    "const seen = new Set();\n"
    "for (const pattern of codePatterns) {\n"
    "  pattern.lastIndex = 0;\n"
    "  let match;\n"
    "  while ((match = pattern.exec(allMessages)) !== null) {\n"
    "    const code = match[0].trim().toUpperCase();\n"
    "    if (!seen.has(code) && code.length >= 4) {\n"
    "      seen.add(code);\n"
    "      detectedCodes.push(code);\n"
    "    }\n"
    "  }\n"
    "}\n\n"
    "// ARAÇ VE VIN TARAMASI\n"
    "const vehicleHints = [];\n"
    "const msgLower = allMessages.toLowerCase();\n"
    "const vehicleKeywords = ['fiat','volkswagen','vw','renault','ford','toyota','hyundai','opel','peugeot','citroen','bmw','mercedes','audi','seat','skoda','egea','doblo','golf','passat','polo','clio','megane','tdi','multijet','dci','1.3','1.6','1.4','2010','2011','2012','2013','2014','2015','2016','2017','2018','2019','2020','2021','2022','2023'];\n"
    "for (const kw of vehicleKeywords) {\n"
    "  if (msgLower.includes(kw)) vehicleHints.push(kw);\n"
    "}\n"
    "const vinPattern = /\\b[A-HJ-NPR-Z0-9]{17}\\b/gi;\n"
    "const detectedVINs = [];\n"
    "let vinMatch;\n"
    "while ((vinMatch = vinPattern.exec(allMessages)) !== null) {\n"
    "  detectedVINs.push(vinMatch[0].toUpperCase());\n"
    "}\n\n"
    "let prompt = '═══ BAĞLAM BİLGİSİ (Sistem Taraması) ═══\\n' +\n"
    "  'Müşteri adı: ' + senderName + '\\n' +\n"
    "  'Batch mesaj sayısı: ' + messageCount + '\\n';\n"
    "if (detectedCodes.length > 0) prompt += '⚠️ TESPİT EDİLEN FİLTRE KODLARI: ' + detectedCodes.join(', ') + '\\n';\n"
    "if (detectedVINs.length > 0) prompt += '🔑 TESPİT EDİLEN ŞASİ NUMARASI: ' + detectedVINs.join(', ') + '\\n';\n"
    "if (vehicleHints.length > 0) prompt += '🚗 ARAÇ İPUCU KELİMELERİ: ' + [...new Set(vehicleHints)].join(', ') + '\\n';\n"
    "if (input.hasImages) prompt += '📸 MÜŞTERİ GÖRSEL GÖNDERDİ: Lütfen görselden okunan parça kodunu (varsa) codeStatus: \"uncertain\" ve source: \"vision\" olarak işaretle.\\n';\n"
    "prompt += '═══════════════════════════════════════\\n\\n';\n"
    "prompt += 'Yeni müşteri mesajları:\\n' + allMessages;\n\n"
    "return [{\n"
    "  json: {\n"
    "    senderNumber: input.senderNumber,\n"
    "    senderName: input.senderName,\n"
    "    allMessagesText: input.allMessagesText,\n"
    "    messageCount: input.messageCount,\n"
    "    batchToken: input.batchToken,\n"
    "    detectedCodes,\n"
    "    detectedVINs,\n"
    "    hasImages: input.hasImages || false,\n"
    "    _prompt: prompt\n"
    "  }\n"
    "}];"
)

ai_agent_system_message = (
    "Sen filtreoto.com WhatsApp satır ve müşteri destek asistanısın. FiltreOto; yalnızca MANN-FILTER, FILTRON, FILTORQ, UFI, HENGST, PURFLUX ve MAHLE markalarının orijinal yağ, hava, yakıt ve polen filtrelerini satan uzman bir e-ticaret platformudur. Kesinlikle motor yağı satışı yapmıyoruz, SADECE FİLTRE satıyoruz.\n\n"
    "GÖREVİN: Müşteri mesajını inceleyerek saf veri çıkarımı yapmak (Extraction) ve taslak yanıt (replyDraft) üretmektir. İş akışı kararlarını ve yönlendirmeleri arka plandaki JavaScript Politika Motoru verecektir.\n\n"
    "SIFIR HALÜSİNASYON VE DOĞRULAMA (VERIFICATION) KURALLARI:\n"
    "1. RAKAMSAL FİYAT VE STOK UYDURMA YASAK: Sistemimizde canlı fiyat listesi sana bağlı olmadığı için KESİNLİKLE \"150 TL\", \"350 TL\" gibi fiyatlar veya hayali stok adedi uydurma!\n"
    "2. Eğer müşteri bir fiyat bilgisi soruyorsa `replyDraft` içinde fiyat verme, yetkili kontrol edileceğini belirt ve JSON'da `verification.priceVerified = false` yap.\n\n"
    "SENARYO VE CASE_TYPE SINIFLANDIRMASI:\n"
    "- exact_code_price_stock: Müşteri net parça kodu verip fiyat veya stok soruyor (Örn: \"MANN W 712/95 var mı, fiyatı nedir?\"). DİKKAT: Bu durumda replyDraft içinde ASLA şasi numarası (VIN) veya araç bilgisi isteme! Usta zaten kodu vermiştir.\n"
    "- exact_code_compatibility: Müşteri parça kodu verip \"Bu kod aracıma uyar mı?\" soruyor.\n"
    "- cross_reference: Müşteri farklı bir kodun veya markanın muadilini soruyor (Örn: \"C 35 154 FILTRON muadili nedir?\").\n"
    "- partial_code: Kod eksik veya belirsiz (Örn: \"712/95\").\n"
    "- vehicle_based_search: Parça kodu vermeden aracı için filtre istiyor (Örn: \"Clio 4 mazot filtresi\").\n"
    "- non_product: İade, şikayet, ödeme sorunu, bayilik veya insan temsilci talebi.\n\n"
    "YALNIZCA GEÇERLİ JSON DÖNDÜR (Markdown ekleme, sadece { ile başlayıp } ile bitir):\n"
    "{\n"
    '  "intent": "price_stock",\n'
    '  "caseType": "exact_code_price_stock",\n'
    '  "entities": {\n'
    '    "productCodes": [\n'
    '      {\n'
    '        "raw": "MANN W 712/95",\n'
    '        "brand": "MANN-FILTER",\n'
    '        "code": "W 712/95",\n'
    '        "codeStatus": "complete",\n'
    '        "source": "customer_text",\n'
    '        "confirmedByCustomer": true,\n'
    '        "extractionConfidence": 1.0\n'
    '      }\n'
    '    ],\n'
    '    "vehicles": [],\n'
    '    "requestedInfo": ["price", "stock"],\n'
    '    "preferredBrands": [],\n'
    '    "quantity": "2 adet"\n'
    '  },\n'
    '  "missingFields": [],\n'
    '  "replyDraft": "İlettiğiniz MANN W 712/95 kodu işleme alınmıştır. Güncel stok ve net fiyat yetkilimiz tarafından kontrol edilerek size iletilecektir; kaç adet istediğinizi paylaşabilir misiniz?",\n'
    '  "confidence": {\n'
    '    "intent": 0.98,\n'
    '    "caseType": 0.97,\n'
    '    "entityExtraction": 0.95\n'
    '  },\n'
    '  "verification": {\n'
    '    "catalogVerified": false,\n'
    '    "stockVerified": false,\n'
    '    "priceVerified": false,\n'
    '    "compatibilityVerified": false,\n'
    '    "dataSource": "customer_message"\n'
    '  }\n'
    '}'
)

parse_ai_output_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const aiOutput = String($input.first().json?.output || '');\n\n"
    "let senderNumber = '';\n"
    "let senderName = '';\n"
    "let allMessagesText = '';\n"
    "let batchToken = '';\n"
    "try {\n"
    "  const sc = $('Store Context').item.json;\n"
    "  senderNumber = String(sc.senderNumber || '');\n"
    "  senderName = String(sc.senderName || senderNumber || 'Bilinmeyen müşteri');\n"
    "  allMessagesText = String(sc.allMessagesText || '');\n"
    "  batchToken = String(sc.batchToken || '');\n"
    "} catch(e) {}\n\n"
    "if (!staticData._unclearCounts) staticData._unclearCounts = {};\n"
    "if (!staticData._batches) staticData._batches = {};\n"
    "if (!staticData._adminNotifications) staticData._adminNotifications = {};\n\n"
    "const batch = staticData._batches[senderNumber];\n"
    "const validClaim = Boolean(batch && batch.processing === true && batch.processingToken === batchToken);\n\n"
    "if (!validClaim && senderNumber) {\n"
    "  return [{ json: {\n"
    "    senderNumber, senderName, batchToken, action: 'ignore', intent: 'other', caseType: 'other',\n"
    "    cevap: '', missingFields: [], confidence: 0, handoffReason: 'Geçersiz veya süresi dolmuş işlem yutuldu',\n"
    "    notifyAdmins: false, validClaim: false, bildirim: ''\n"
    "  }}];\n"
    "}\n\n"
    "let parsed = null;\n"
    "try {\n"
    "  const cleaned = aiOutput.replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```$/i, '').trim();\n"
    "  parsed = JSON.parse(cleaned);\n"
    "} catch (e1) {\n"
    "  try {\n"
    "    const match = aiOutput.match(/\\{[\\s\\S]*\\}/);\n"
    "    if (match) parsed = JSON.parse(match[0]);\n"
    "  } catch(e2) {}\n"
    "}\n\n"
    "if (!parsed) {\n"
    "  return [{ json: {\n"
    "    senderNumber, senderName, batchToken, action: 'handoff', intent: 'unclear', caseType: 'unclear',\n"
    "    cevap: 'Talebinizi ilgili ekibimize aktarıyorum. Yetkilimiz sizinle ilgilenecektir.',\n"
    "    missingFields: [], confidence: 0, handoffReason: 'AI JSON ayrıştırma hatası',\n"
    "    notifyAdmins: true, validClaim: true, pauseAutomation: true,\n"
    "    bildirim: `⚠️ AI ÇIKTISI AYRIŞTIRILAMADI\\nMüşteri: ${senderName} (${senderNumber})\\nMesaj: ${allMessagesText}`\n"
    "  }}];\n"
    "}\n\n"
    "const intent = String(parsed.intent || 'other').trim();\n"
    "const caseType = String(parsed.caseType || intent || 'other').trim();\n"
    "const entities = parsed.entities || {};\n"
    "let replyDraft = String(parsed.replyDraft || parsed.reply || parsed.cevap || '').trim();\n"
    "const missingFields = Array.isArray(parsed.missingFields) ? parsed.missingFields.slice(0, 10) : [];\n"
    "const verification = parsed.verification || {};\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// LAYER 2 GUARDRAIL: PROVENANCE & HALLUCINATION INTERCEPTOR\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "let guardrailTriggered = false;\n"
    "let triggeredRule = '';\n"
    "const PRICE_PATTERN = /(?:₺\\s*\\d+(?:[\\.,]\\d+)?|\\d+(?:[\\.,]\\d+)?\\s*(?:TL|₺|TRY|Lira))/i;\n"
    "const BANNED_PHRASES = ['stokta var', 'stoklarımızda mevcut', 'kesin uyar', 'uyumludur', 'birebir muadilidir', 'yerine kullanabilirsiniz'];\n\n"
    "if (verification.priceVerified !== true && PRICE_PATTERN.test(replyDraft)) {\n"
    "  guardrailTriggered = true;\n"
    "  triggeredRule = 'Doğrulanmamış rakamsal fiyat/TL halüsinasyonu';\n"
    "} else if (verification.stockVerified !== true || verification.compatibilityVerified !== true) {\n"
    "  const replyLower = replyDraft.toLocaleLowerCase('tr-TR');\n"
    "  for (const phrase of BANNED_PHRASES) {\n"
    "    if (replyLower.includes(phrase.toLocaleLowerCase('tr-TR'))) {\n"
    "      guardrailTriggered = true;\n"
    "      triggeredRule = `Yasaklı stok/uyumluluk garantisi ('${phrase}')`;\n"
    "      break;\n"
    "    }\n"
    "  }\n"
    "}\n\n"
    "if (guardrailTriggered) {\n"
    "  replyDraft = 'Ürünün güncel stok, fiyat ve teknik uygunluk bilgisi yetkilimiz tarafından kontrol edilerek size iletilecektir.';\n"
    "}\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// JAVASCRIPT POLITIKA MOTORU (POLICY ENGINE MATRIX)\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "let requiresHumanAction = false;\n"
    "let notifyAdmin = false;\n"
    "let pauseAutomation = false;\n"
    "let askVehicleInfo = false;\n"
    "let action = 'reply';\n"
    "let handoffReason = guardrailTriggered ? `Guardrail Müdahalesi: ${triggeredRule}` : '';\n\n"
    "if (guardrailTriggered) {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = false;\n"
    "} else if (caseType === 'exact_code_price_stock') {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = false;\n"
    "  askVehicleInfo = false; // KESİNLİKLE ŞASİ İSTEME!\n"
    "  if (/şasi|vin|araç model/i.test(replyDraft)) {\n"
    "    replyDraft = 'İlettiğiniz parça kodları işleme alınmıştır. Güncel stok ve net fiyat yetkilimiz tarafından kontrol edilerek size iletilecektir; kaç adet istediğinizi paylaşabilir misiniz?';\n"
    "  }\n"
    "} else if (caseType === 'exact_code_compatibility') {\n"
    "  const hasVehicles = entities.vehicles && entities.vehicles.length > 0;\n"
    "  if (!hasVehicles) {\n"
    "    requiresHumanAction = false;\n"
    "    notifyAdmin = false;\n"
    "    pauseAutomation = false;\n"
    "    askVehicleInfo = true;\n"
    "  } else {\n"
    "    requiresHumanAction = true;\n"
    "    notifyAdmin = true;\n"
    "    pauseAutomation = false;\n"
    "    askVehicleInfo = false;\n"
    "  }\n"
    "} else if (caseType === 'cross_reference') {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = false;\n"
    "  askVehicleInfo = false;\n"
    "} else if (caseType === 'partial_code') {\n"
    "  requiresHumanAction = false;\n"
    "  notifyAdmin = false;\n"
    "  pauseAutomation = false;\n"
    "} else if (caseType === 'vehicle_based_search') {\n"
    "  const hasVehicles = entities.vehicles && entities.vehicles.length > 0;\n"
    "  if (!hasVehicles) {\n"
    "    requiresHumanAction = false;\n"
    "    notifyAdmin = false;\n"
    "    pauseAutomation = false;\n"
    "    askVehicleInfo = true;\n"
    "  } else {\n"
    "    requiresHumanAction = true;\n"
    "    notifyAdmin = true;\n"
    "    pauseAutomation = false;\n"
    "  }\n"
    "} else if (caseType === 'non_product' || intent === 'return_complaint' || intent === 'wholesale') {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = true; // Şikayet, iade veya temsilci talebinde botu sustur\n"
    "  action = 'handoff';\n"
    "  handoffReason = `Özel durum veya temsilci talebi (${intent})`;\n"
    "} else if (intent === 'unclear') {\n"
    "  staticData._unclearCounts[senderNumber] = Number(staticData._unclearCounts[senderNumber] || 0) + 1;\n"
    "  if (staticData._unclearCounts[senderNumber] >= 2) {\n"
    "    requiresHumanAction = true;\n"
    "    notifyAdmin = true;\n"
    "    pauseAutomation = true;\n"
    "    action = 'handoff';\n"
    "    handoffReason = 'Talep 2 kez üst üste anlaşılamadı';\n"
    "    replyDraft = 'Talebinizi doğru yönlendirebilmek için ilgili ekibimize aktarıyorum. Yetkilimiz sizinle ilgilenecektir.';\n"
    "  }\n"
    "} else if (intent === 'greeting') {\n"
    "  requiresHumanAction = false;\n"
    "  notifyAdmin = false;\n"
    "  pauseAutomation = false;\n"
    "}\n\n"
    "if (intent !== 'unclear') delete staticData._unclearCounts[senderNumber];\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// SPAM KORUMASI, COOLDOWN VE GÜNCELLEME BİLDİRİMİ\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "const now = Date.now();\n"
    "const lastNotif = staticData._adminNotifications[senderNumber];\n"
    "let isUpdate = false;\n"
    "let shouldNotifyAdmin = notifyAdmin;\n\n"
    "const currentCodes = Array.isArray(entities.productCodes) ? entities.productCodes.map(c => typeof c === 'object' ? c.code || c.raw : c).filter(Boolean) : [];\n"
    "const quantity = String(entities.quantity || 'Belirtilmedi');\n\n"
    "if (notifyAdmin && lastNotif && (now - Number(lastNotif.timestamp) < 3 * 60 * 1000)) {\n"
    "  const oldCodes = lastNotif.codes || [];\n"
    "  const addedCodes = currentCodes.filter(c => !oldCodes.includes(c));\n"
    "  const qtyChanged = lastNotif.quantity !== quantity && quantity !== 'Belirtilmedi';\n"
    "  if (addedCodes.length > 0 || qtyChanged || caseType !== lastNotif.caseType) {\n"
    "    isUpdate = true;\n"
    "    shouldNotifyAdmin = true;\n"
    "  } else {\n"
    "    shouldNotifyAdmin = false; // 3 dk içindeki aynen mükerrer bildirimleri engelle\n"
    "  }\n"
    "}\n\n"
    "if (notifyAdmin && shouldNotifyAdmin) {\n"
    "  staticData._adminNotifications[senderNumber] = {\n"
    "    timestamp: now,\n"
    "    caseType,\n"
    "    codes: currentCodes,\n"
    "    quantity\n"
    "  };\n"
    "}\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// DİNAMİK YÖNETİCİ BİLDİRİM ŞABLONU INŞASI\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "let headerTitle = '📢 MÜŞTERİ TALEBİ / BİLDİRİM';\n"
    "let yetkiliAksiyonu = 'Talep inceleme ve dönüş yapma';\n"
    "if (isUpdate) {\n"
    "  headerTitle = '🔄 SATIŞ TALEBİ GÜNCELLENDİ';\n"
    "} else if (caseType === 'exact_code_price_stock' || currentCodes.length > 0) {\n"
    "  headerTitle = '🔥 YÜKSEK NİYETLİ SATIŞ TALEBİ';\n"
    "  yetkiliAksiyonu = 'Stok ve net fiyat kontrolü';\n"
    "} else if (caseType === 'exact_code_compatibility' || intent === 'product_compatibility') {\n"
    "  headerTitle = '🛠️ UYUMLULUK VE PARÇA KONTROLÜ';\n"
    "  yetkiliAksiyonu = 'Şasi/Araç uyumluluk teyidi ve parça tespiti';\n"
    "} else if (intent === 'return_complaint' || caseType === 'non_product') {\n"
    "  headerTitle = '⚠️ ŞİKAYET / İADE / TEMSİLCİ TALEBİ';\n"
    "  yetkiliAksiyonu = 'Müşteri memnuniyeti / İade prosedürü kontrolü';\n"
    "}\n\n"
    "const formattedCodes = currentCodes.length > 0 ? currentCodes.map(c => `• ${c}`).join(' ') : 'Belirtilmedi';\n"
    "const formattedVehicles = Array.isArray(entities.vehicles) && entities.vehicles.length > 0 ? entities.vehicles.map(v => typeof v === 'object' ? `• ${v.brand || ''} ${v.model || ''} ${v.year || ''}`.trim() : `• ${v}`).join(' ') : (caseType === 'exact_code_price_stock' ? 'Gerekli değil (Tam kod verildi)' : 'Belirtilmedi');\n\n"
    "const bildirim = `${headerTitle}\\n` +\n"
    "  `Müşteri: ${senderName} (${senderNumber})\\n` +\n"
    "  `Talep türü: ${caseType}\\n` +\n"
    "  `Kodlar: ${formattedCodes}\\n` +\n"
    "  `Miktar: ${quantity}\\n` +\n"
    "  `Araç bilgisi: ${formattedVehicles}\\n` +\n"
    "  `Yetkili aksiyonu: ${yetkiliAksiyonu}\\n\\n` +\n"
    "  `📌 AI Özeti: ${allMessagesText.replace(/\\s+/g, ' ').slice(0, 160)}\\n` +\n"
    "  `🤖 AI Cevabı: ${replyDraft}`;\n\n"
    "return [{\n"
    "  json: {\n"
    "    senderNumber,\n"
    "    senderName,\n"
    "    batchToken,\n"
    "    action,\n"
    "    intent,\n"
    "    caseType,\n"
    "    entities,\n"
    "    cevap: replyDraft,\n"
    "    bildirim,\n"
    "    missingFields,\n"
    "    handoffReason,\n"
    "    requiresHumanAction,\n"
    "    pauseAutomation,\n"
    "    notifyAdmins: shouldNotifyAdmin === true,\n"
    "    validClaim: true\n"
    "  }\n"
    "}];"
)

clear_batch_js = (
    "const input = $input.first().json;\n"
    "const staticData = $getWorkflowStaticData('global');\n"
    "const senderNumber = String(input.senderNumber || '');\n\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n\n"
    "// Handoff veya pauseAutomation tetiklendiyse müşteriyi manuel moda kilitliyoruz\n"
    "if (input.pauseAutomation === true || input.action === 'handoff') {\n"
    "  staticData._manualModes[senderNumber] = true;\n"
    "  staticData._manualModes = Object.assign({}, staticData._manualModes);\n"
    "  if (staticData._batches && senderNumber) delete staticData._batches[senderNumber];\n"
    "} else if (staticData._batches && staticData._batches[senderNumber]) {\n"
    "  const batch = staticData._batches[senderNumber];\n"
    "  batch.processingMessages = [];\n"
    "  batch.processing = false;\n"
    "  batch.processingToken = null;\n"
    "  batch.processingStartedAt = null;\n"
    "  if (!Array.isArray(batch.pendingMessages) || batch.pendingMessages.length === 0) {\n"
    "    delete staticData._batches[senderNumber];\n"
    "  }\n"
    "}\n\n"
    "return [{ json: input }];"
)

idle_timeout_check_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const now = Date.now();\n"
    "const idleAlertMs = 10 * 60 * 1000;\n\n"
    "if (!staticData._lastReply) staticData._lastReply = {};\n"
    "const alerts = [];\n"
    "for (const [number, lastReplyTime] of Object.entries(staticData._lastReply)) {\n"
    "  if (now - lastReplyTime >= idleAlertMs) {\n"
    "    alerts.push({\n"
    "      json: {\n"
    "        senderNumber: number,\n"
    "        bildirim: `Sessiz müşteri - ${number} - 10 dakikadır yanıt vermiyor`,\n"
    "        _idleAlert: true\n"
    "      }\n"
    "    });\n"
    "    delete staticData._lastReply[number];\n"
    "  }\n"
    "}\n"
    "if (alerts.length === 0) return [{ json: { _idleAlert: false } }];\n"
    "return alerts;"
)

# ── Node Definitions ──
nodes = [
    {
        "parameters": {"httpMethod": "POST", "path": "evolution-webhook", "responseMode": "responseNode", "options": {}},
        "id": get_node_id("Webhook1"), "name": "Webhook1",
        "type": "n8n-nodes-base.webhook", "typeVersion": 1.1,
        "position": [240, 640], "webhookId": "b543e85d-b182-4ddd-af94-3f124a6c2c82"
    },
    {
        "parameters": {"respondWith": "json", "responseBody": "={\"status\":\"ok\"}", "options": {}},
        "id": get_node_id("Respond OK1"), "name": "Respond OK1",
        "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1, "position": [240, 432]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [
                    {"id": "cond-allow", "leftValue": "={{ !$json.body.data.key.fromMe || ['++', '--'].includes($json.body.data.message?.conversation || $json.body.data.message?.extendedTextMessage?.text || '') }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}},
                    {"id": "cond-no-group", "leftValue": "={{ $json.body.data.key.remoteJid }}", "rightValue": "@g.us", "operator": {"type": "string", "operation": "notEndsWith"}}
                ],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("fromMe Check"), "name": "fromMe Check",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [528, 640]
    },
    {
        "parameters": {"jsCode": batch_collector_js},
        "id": get_node_id("Batch Collector"), "name": "Batch Collector",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [768, 640]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [{"id": "cond-action", "leftValue": "={{ $json._action }}", "rightValue": "process", "operator": {"type": "string", "operation": "equals"}}],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("Should Process?"), "name": "Should Process?",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [1008, 640]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [{"id": "cond-cmd", "leftValue": "={{ $json._action }}", "rightValue": "command", "operator": {"type": "string", "operation": "equals"}}],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("Is Command?"), "name": "Is Command?",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [1008, 960]
    },
    {
        "parameters": {"jsCode": store_context_js},
        "id": get_node_id("Store Context"), "name": "Store Context",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1248, 640]
    },
    {
        "parameters": {
            "promptType": "define", "text": "={{ $json._prompt }}",
            "options": {"systemMessage": ai_agent_system_message}
        },
        "type": "@n8n/n8n-nodes-langchain.agent", "typeVersion": 3.1,
        "position": [1472, 624], "id": get_node_id("AI Agent"), "name": "AI Agent"
    },
    {
        "parameters": {
            "model": {"__rl": True, "value": "gpt-4o-mini", "mode": "list", "cachedResultName": "gpt-4o-mini"},
            "builtInTools": {}, "options": {"temperature": 0.1, "maxTokens": 600}
        },
        "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi", "typeVersion": 1.3,
        "position": [1392, 864], "id": get_node_id("OpenAI Chat Model1"), "name": "OpenAI Chat Model1",
        "credentials": {"openAiApi": {"id": "3M52tD49lJ35vXdO", "name": "OpenAi account"}}
    },
    {
        "parameters": {
            "sessionIdType": "customKey",
            "sessionKey": "={{ $('Store Context').item.json.senderNumber }}",
            "contextWindowLength": 20
        },
        "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow", "typeVersion": 1.3,
        "position": [1552, 864], "id": get_node_id("Simple Memory"), "name": "Simple Memory"
    },
    {
        "parameters": {"jsCode": parse_ai_output_js},
        "id": get_node_id("Parse AI Output"), "name": "Parse AI Output",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1808, 624]
    },
    {
        "parameters": {"jsCode": clear_batch_js},
        "id": get_node_id("Clear Batch"), "name": "Clear Batch",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2032, 624]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [{"id": "cond-notify", "leftValue": "={{ $json.notifyAdmins === true }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("Should Notify Admins?"), "name": "Should Notify Admins?",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [2240, 520]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [
                    {"id": "cond-reply-action", "leftValue": "={{ $json.action }}", "rightValue": "ignore", "operator": {"type": "string", "operation": "notEquals"}},
                    {"id": "cond-reply-text", "leftValue": "={{ $json.cevap }}", "rightValue": "", "operator": {"type": "string", "operation": "notEquals"}}
                ],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("Should Reply Customer?"), "name": "Should Reply Customer?",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [2240, 780]
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "089311B617B8-48CF-8BD6-29759A57FDBF"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905052237182', text: $json.bildirim }) }}",
            "options": {"timeout": 30000, "batching": {"batch": {"batchSize": 1, "batchInterval": 100}}}
        },
        "id": get_node_id("Phone A Send"), "name": "Phone A Send",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2480, 416]
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "089311B617B8-48CF-8BD6-29759A57FDBF"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905306056066', text: $json.bildirim }) }}",
            "options": {"timeout": 30000}
        },
        "id": get_node_id("Phone B Send"), "name": "Phone B Send",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2480, 624]
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "089311B617B8-48CF-8BD6-29759A57FDBF"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: $json.senderNumber, text: $json.cevap }) }}",
            "options": {"timeout": 30000}
        },
        "id": get_node_id("Reply to Customer"), "name": "Reply to Customer",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2480, 864]
    },
    {
        "parameters": {"rule": {"interval": [{"field": "seconds", "secondsInterval": 15}]}},
        "id": get_node_id("Schedule Trigger"), "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [240, 1104]
    },
    {
        "parameters": {"jsCode": stale_batch_check_js},
        "id": get_node_id("Stale Batch Check"), "name": "Stale Batch Check",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [528, 1104]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [{"id": "cond-stale", "leftValue": "={{ $json.messageCount }}", "rightValue": 0, "operator": {"type": "number", "operation": "gt"}}],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("Stale Exists?"), "name": "Stale Exists?",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [768, 1104]
    },
    {
        "parameters": {"jsCode": idle_timeout_check_js},
        "id": get_node_id("Idle Timeout Check"), "name": "Idle Timeout Check",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [528, 1360]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [{"id": "cond-idle", "leftValue": "={{ $json._idleAlert }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("Idle Alert?"), "name": "Idle Alert?",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [768, 1360]
    },
]

# ── Connections ──
connections = {
    "Webhook1": {"main": [[{"node": "Respond OK1", "type": "main", "index": 0}, {"node": "fromMe Check", "type": "main", "index": 0}]]},
    "fromMe Check": {"main": [[{"node": "Batch Collector", "type": "main", "index": 0}], []]},
    "Batch Collector": {"main": [[{"node": "Should Process?", "type": "main", "index": 0}, {"node": "Is Command?", "type": "main", "index": 0}]]},
    "Should Process?": {"main": [[{"node": "Store Context", "type": "main", "index": 0}], []]},
    "Is Command?": {"main": [[{"node": "Phone A Send", "type": "main", "index": 0}, {"node": "Phone B Send", "type": "main", "index": 0}], []]},
    "Store Context": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
    "AI Agent": {"main": [[{"node": "Parse AI Output", "type": "main", "index": 0}]]},
    "Parse AI Output": {"main": [[{"node": "Clear Batch", "type": "main", "index": 0}]]},
    "Clear Batch": {"main": [[{"node": "Should Notify Admins?", "type": "main", "index": 0}, {"node": "Should Reply Customer?", "type": "main", "index": 0}]]},
    "Should Notify Admins?": {"main": [[{"node": "Phone A Send", "type": "main", "index": 0}, {"node": "Phone B Send", "type": "main", "index": 0}], []]},
    "Should Reply Customer?": {"main": [[{"node": "Reply to Customer", "type": "main", "index": 0}], []]},
    "Schedule Trigger": {"main": [[{"node": "Stale Batch Check", "type": "main", "index": 0}, {"node": "Idle Timeout Check", "type": "main", "index": 0}]]},
    "Stale Batch Check": {"main": [[{"node": "Stale Exists?", "type": "main", "index": 0}]]},
    "Stale Exists?": {"main": [[{"node": "Store Context", "type": "main", "index": 0}], []]},
    "Idle Timeout Check": {"main": [[{"node": "Idle Alert?", "type": "main", "index": 0}]]},
    "Idle Alert?": {"main": [[{"node": "Phone A Send", "type": "main", "index": 0}, {"node": "Phone B Send", "type": "main", "index": 0}], []]},
    "OpenAI Chat Model1": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
    "Simple Memory": {"ai_memory": [[{"node": "AI Agent", "type": "ai_memory", "index": 0}]]},
}

# ── Build ──
try:
    with open("workflow.json", "r", encoding="utf-8") as f:
        wf = json.load(f)
except Exception:
    wf = {}

wf["nodes"] = nodes
wf["connections"] = connections
wf["settings"] = {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveExecutionProgress": True, "saveManualExecutions": True}
if "staticData" not in wf or not wf["staticData"]:
    wf["staticData"] = {"node:Schedule Trigger": {"recurrenceRules": []}, "global": {"_batches": {}}}
wf["meta"] = {"templateCredsSetupCompleted": True}
wf["pinData"] = {}

with open("workflow.json", "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)

print(f"workflow.json v11 Enterprise generated: {len(nodes)} nodes, {len(connections)} connection sources")
