import json
import uuid
import os

# ── Node IDs (stable, reused from n8n) ──
node_ids = {
    "Webhook1": "65f757d5-7045-45df-90aa-a959a4a10519",
    "Respond OK1": "c370ae94-67de-411e-8368-4d479f00e421",
    "fromMe Check": "5527d4b8-019e-4bb6-bbd3-526fab1f9470",
    "Batch Collector": "cf3dc39b-5fa7-5389-ac72-94e2862a9cc2",
    "Should Process?": "6d6eba4b-4ded-5387-8f29-7d518c86632f",
    "Is Command?": "cc-001-cmd-check",
    "Delete Command Message": "cmd-delete-message-node",
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
    "const senderNumber = rawJid.replace('@s.whatsapp.net', '').replace('@g.us', '').replace('@lid', '');\n"
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
    "// Deduplication Check (TTL + Size Limit)\n"
    "if (messageId && staticData._seenMessageIds[messageId]) {\n"
    "  return [{ json: { _action: 'ignore', reason: 'duplicate_message', messageId } }];\n"
    "}\n"
    "if (messageId) {\n"
    "  staticData._seenMessageIds[messageId] = now;\n"
    "  const seenTtlMs = 6 * 60 * 60 * 1000; // 6 saat TTL\n"
    "  const cleanupIntervalMs = 5 * 60 * 1000;\n"
    "  const lastCleanupAt = Number(staticData._lastSeenCleanupAt || 0);\n"
    "  if (now - lastCleanupAt >= cleanupIntervalMs) {\n"
    "    for (const [id, seenAt] of Object.entries(staticData._seenMessageIds)) {\n"
    "      if (now - Number(seenAt || 0) > seenTtlMs) delete staticData._seenMessageIds[id];\n"
    "    }\n"
    "    staticData._lastSeenCleanupAt = now;\n"
    "  }\n"
    "  const ids = Object.keys(staticData._seenMessageIds);\n"
    "  if (ids.length > 3000) {\n"
    "    ids.sort((a, b) => staticData._seenMessageIds[a] - staticData._seenMessageIds[b])\n"
    "       .slice(0, ids.length - 2500)\n"
    "       .forEach(id => delete staticData._seenMessageIds[id]);\n"
    "  }\n"
    "}\n\n"
    "// === YETKİLİ KULLANICI KONTROLÜ (fromMe veya Yönetici Numaraları) ===\n"
    "const ownerNumbers = ['905052237182', '905306056066', '905363955525'];\n"
    "const isAuthorized = fromMe || ownerNumbers.includes(senderNumber);\n\n"
    "// === ++/-- KOMUTLARI: YALNIZCA YETKİLİ İSE KOMUT OLARAK İŞLE (CMD-001) ===\n"
    "if (isAuthorized && messageText === '++') {\n"
    "  staticData._manualModes[senderNumber] = true;\n"
    "  delete staticData._batches[senderNumber];\n"
    "  return [{ json: {\n"
    "    _action: 'command',\n"
    "    senderNumber: senderNumber,\n"
    "    command: 'paused',\n"
    "    commandMessageId: messageId,\n"
    "    commandFromMe: fromMe,\n"
    "    commandRemoteJid: rawJid,\n"
    "    commandParticipant: input.body.data.key.participant || '',\n"
    "    bildirim: 'Sistem Manuel De - ' + senderName + ' (' + senderNumber + ')'\n"
    "  }}];\n"
    "}\n\n"
    "if (isAuthorized && messageText === '--') {\n"
    "  delete staticData._manualModes[senderNumber];\n"
    "  return [{ json: {\n"
    "    _action: 'command',\n"
    "    senderNumber: senderNumber,\n"
    "    command: 'resumed',\n"
    "    commandMessageId: messageId,\n"
    "    commandFromMe: fromMe,\n"
    "    commandRemoteJid: rawJid,\n"
    "    commandParticipant: input.body.data.key.participant || '',\n"
    "    bildirim: 'Sistem Otomatik - ' + senderName + ' (' + senderNumber + ')'\n"
    "  }}];\n"
    "}\n\n"
    "if (fromMe || staticData._manualModes[senderNumber] === true) {\n"
    "  return [{ json: { _action: 'ignore' } }];\n"
    "}\n\n"
    "// === IDL-002: Müşteriden yeni mesaj (!fromMe) geldiyse idle sayacını sil ===\n"
    "if (!fromMe && staticData._lastReply && staticData._lastReply[senderNumber]) {\n"
    "  delete staticData._lastReply[senderNumber];\n"
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
    "// BAT-001: Fast-path bozukluğunu engelle, tüm batch işlemlerini Stale Batch Check (claimBatch) yapsın\n"
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
    "const BATCH_WINDOW_MS    = 120 * 1000;     // İlk mesajdan itibaren sabit 120 sn toplama penceresi\n"
    "const PROCESSING_TIMEOUT = 2 * 60 * 1000;  // 2 dk AI işlem timeout recovery\n\n"
    "if (!staticData._batches) staticData._batches = {};\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n"
    "for (const [number, enabled] of Object.entries(staticData._manualModes)) {\n"
    "  if (enabled !== true) delete staticData._manualModes[number];\n"
    "}\n\n"
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
    "  const startTime = Number(batch.pendingStartedAt || batch.startTime || now);\n"
    "  const totalTime = now - startTime;\n\n"
    "  const isWindowReached = totalTime >= BATCH_WINDOW_MS;\n\n"
    "  if (isWindowReached) {\n"
    "    ready.push({ number, lastTime: Number(batch.lastMessageAt || batch.lastMessageTime || now), batch, triggeredBy: '120_second_window' });\n"
    "  }\n"
    "}\n\n"
    "ready.sort((a, b) => a.lastTime - b.lastTime);\n"
    "if (ready.length === 0) {\n"
    "  return [{ json: { senderNumber: '', messageCount: 0, _ready: false } }];\n"
    "}\n\n"
    "const outputItems = [];\n"
    "const batchLimit = Math.min(ready.length, 10);\n"
    "for (let i = 0; i < batchLimit; i++) {\n"
    "  const selected = ready[i];\n"
    "  const { number, batch } = selected;\n"
    "  const processingMessages = batch.pendingMessages.splice(0);\n"
    "  const processingToken = number + '-' + now + '-' + Math.random().toString(36).slice(2, 10);\n\n"
    "  batch.processingMessages = processingMessages;\n"
    "  batch.processing = true;\n"
    "  batch.processingStartedAt = now;\n"
    "  batch.processingToken = processingToken;\n"
    "  batch.pendingStartedAt = null;\n"
    "  // n8n VM proxy'sinin staticData'yı veritabanına yazması için dirty flag tetikle\n"
    "  staticData._batches = Object.assign({}, staticData._batches);\n\n"
    "  const allMessagesText = processingMessages\n"
    "    .map((message, index) => `${index + 1}. [${message.time || ''}] ${message.text}`)\n"
    "    .join('\\n');\n\n"
    "  const hasImages = processingMessages.some(m => m.type === 'image');\n"
    "  const imageMessages = processingMessages\n"
    "    .filter(m => m.type === 'image' && m.mediaUrl)\n"
    "    .map(m => ({ mediaUrl: m.mediaUrl, mediaKey: m.mediaKey, mimetype: m.mimetype }));\n\n"
    "  outputItems.push({\n"
    "    json: {\n"
    "      _ready: true,\n"
    "      senderNumber: number,\n"
    "      senderName: batch.senderName || number,\n"
    "      messageCount: processingMessages.length,\n"
    "      allMessagesText,\n"
    "      batchToken: processingToken,\n"
    "      hasImages,\n"
    "      imageMessages\n"
    "    }\n"
    "  });\n"
    "}\n"
    "return outputItems;"
)


store_context_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const expectedSecret = staticData._webhookSecret || process.env.N8N_WEBHOOK_SECRET || '';\n\n"
    "if (!expectedSecret) {\n"
    "    const input = $input.item.json;\n"
    "    return [{ json: input }];\n"
    "}\n\n"
    "const input = $input.first().json;\n"
    "const queryToken = input?.query?.token || '';\n"
    "const headerToken = input?.headers?.['x-webhook-secret'] || '';\n"
    "const bodySecret = input?.body?.secret || '';\n"
    "const providedSecret = queryToken || headerToken || bodySecret;\n"
    "if (providedSecret !== expectedSecret) {\n"
    "    throw new Error('Webhook authentication failed: Invalid secret');\n"
    "}\n\n"
    "const allMessages  = String(input.allMessagesText || '');\n"
    "const messageCount = Number(input.messageCount || 0);\n"
    "const senderName   = String(input.senderName || '');\n\n"
    "// FİLTRE KODU PATTERN TARAMASI (REG-001, REG-002, REG-003)\n"
    "const codePatterns = [\n"
    "  /\\b(?:MANN[-\\s]?)?(?:W|C|HU|WK|PU|PL|FP|CU|CUK|H)\\s?\\d{1,4}(?:\\s?\\d{2,4})?(?:\\s?[\\/\\-]\\s?\\d{1,2})?(?:\\s?[xXzZ])?\\b/gi,\n"
    "  /\\b(?:FILTRON[-\\s]?)?(?:OP|P|OS|OW|PS|WS|AS|AP|L|LS)\\s?\\d{3,4}(?:\\s?[\\/\\-]\\s?\\d{1,2})?\\b/gi,\n"
    "  /\\b(?:UFI[-\\s]?)?\\d{2}\\.\\d{2,3}\\.\\d{2}(?:[\\/\\-]\\d)?\\b/gi,\n"
    "  /\\b(?:HENGST[-\\s]?)?E\\s?\\d{2,4}[A-Z0-9]*(?:\\s?D?\\s?\\d{2,3}[A-Z]?)?\\b/gi,\n"
    "  /\\b(?:PURFLUX[-\\s]?)?LS\\s?\\d{3,4}(?:[\\/\\-]\\d{1,2})?\\b/gi,\n"
    "  /\\b(?:MAHLE[-\\s]?)?(?:OX|OC|KC|KL|KX|PI|LS|W)\\s?\\d{2,4}[A-Z]?\\b/gi,\n"
    "  /\\b(?:FILTORQ[-\\s]?)?[A-Z]{1,3}\\s?\\d{3,4}(?:[\\/\\-]\\d{1,2})?\\b/gi,\n"
    "  /\\b[A-Z]{1,4}\\s?\\d{2,5}[\\/\\-]\\d{2,5}(?:\\s?(?:KIT|SET|PRO))?\\b/gi,\n"
    "  /\\b(?!(?:201[0-9]|202[0-6])\\b)\\d{3,4}\\s?[\\/\\-]\\s?\\d{1,2}\\b/g\n"
    "];\n\n"
    "const rawCandidates = [];\n"
    "for (const pattern of codePatterns) {\n"
    "  pattern.lastIndex = 0;\n"
    "  let match;\n"
    "  while ((match = pattern.exec(allMessages)) !== null) {\n"
    "    const code = match[0].trim().toUpperCase();\n"
    "    // REG-003: Araç model yılları (2010..2026) ve 4 karakterden kısa kodları ele\n"
    "    if (code.length >= 4 && !/\\b20(1[0-9]|2[0-6])\\b/.test(code)) {\n"
    "      rawCandidates.push(code);\n"
    "    }\n"
    "  }\n"
    "}\n\n"
    "// REG-004: Sub-part tekilleştirme (En uzun koddan başla, kapsanan alt parçaları atla)\n"
    "const uniqueCandidates = [...new Set(rawCandidates)].sort((a, b) => b.length - a.length);\n"
    "const detectedCodes = [];\n"
    "for (const code of uniqueCandidates) {\n"
    "  if (!detectedCodes.some(selected => selected.includes(code))) {\n"
    "    detectedCodes.push(code);\n"
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
    "// VIS-001: Görsel işleme modelinin bulunmadığına dair net talimat\n"
    "if (input.hasImages) prompt += '📸 MÜŞTERİ GÖRSEL GÖNDERDİ: Sistemde henüz doğrudan görsel işleme (vision model) aktif değildir. Görselden parça kodu veya marka KESİNLİKLE UYDURMA/HALÜSİNASYON YAPMA! Eğer mesaj metninde net bir parça kodu yoksa, replyDraft içinde tam olarak \"Görsel ulaştı. Ürün üzerindeki marka ve parça kodunu yazılı olarak paylaşabilir misiniz?\" cevabını ver (ve codeStatus: \"uncertain\", source: \"vision\" olarak işaretle).\\n';\n"
    "prompt += '═══════════════════════════════════════\\n\\n';\n"
    "prompt += 'Yeni müşteri mesajları:\\n' + allMessages;\n\n"
    "return {\n"
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
    "};"
)



ai_agent_system_message = (
    "Sen filtreoto.com WhatsApp satır ve müşteri destek asistanısın. FiltreOto; yalnızca MANN-FILTER, FILTRON, FILTORQ, UFI, HENGST, PURFLUX ve MAHLE markalarının orijinal yağ, hava, yakıt ve polen filtrelerini satan uzman bir e-ticaret platformudur. Kesinlikle motor yağı satışı yapmıyoruz, SADECE FİLTRE satıyoruz.\n\n"
    "GÖREVİN: Müşteri mesajını inceleyerek saf veri çıkarımı yapmak (Extraction) ve taslak yanıt (replyDraft) üretmektir. İş akışı kararlarını ve yönlendirmeleri arka plandaki JavaScript Politika Motoru verecektir.\n\n"
    "SIFIR HALÜSİNASYON VE DOĞRULAMA (VERIFICATION) KURALLARI:\n"
    "1. RAKAMSAL FİYAT VE STOK UYDURMA YASAK: Sistemimizde canlı fiyat listesi sana bağlı olmadığı için KESİNLİKLE \"150 TL\", \"350 TL\" gibi fiyatlar veya hayali stok adedi uydurma!\n"
    "2. Eğer müşteri bir fiyat bilgisi soruyorsa `replyDraft` içinde fiyat verme, yetkili kontrol edileceğini belirt ve JSON'da `verification.priceVerified = false` yap.\n"
    "3. GÖRSEL / FOTOĞRAF (VISION) KURALLARI (`hasImages === true`): Sistemde henüz doğrudan görsel işleme (binary vision model) aktif olmadığı için, müşteri görsel/fotoğraf gönderdiğinde KESİNLİKLE görmediğin görselden parça kodu veya marka uydurma/halüsinasyon yapma! Eğer müşteri mesaj metninde net bir parça kodu yazmadıysa, `replyDraft` içinde tam olarak `\"Görsel ulaştı. Ürün üzerindeki marka ve parça kodunu yazılı olarak paylaşabilir misiniz?\"` yanıtını ver ve `codeStatus: \"uncertain\"`, `source: \"vision\"` olarak işaretle.\n\n"
    "İÇERİK, KONUM VE ORİJİNALLİK GARANTİSİ KURALLARI (BUSINESS KNOWLEDGE):\n"
    "1. KONUM VE SEVKİYAT BİLGİSİ (`DOC-001`): Müşteri nereden gönderim yapıldığını, adresimizi veya mağaza konumumuzu sorduğunda veya sevkiyatla ilgili bilgi gerektiğinde `Ankara Şaşmaz / İvedik OSB veya Ankara depomuzdan Türkiye geneline gönderim yapmaktayız` bilgisini net bir şekilde ilet.\n"
    "2. ORİJİNAL MARKA GARANTİSİ POLİTİKASI (`DOC-002`): Müşteri ürünlerin orijinalliğini, garantisini veya hangi markalarla çalıştığımızı sorduğunda `Sattığımız tüm ürünler MANN-FILTER, FILTRON, FILTORQ, UFI, HENGST, PURFLUX ve MAHLE markalarının %100 orijinal, faturalı ve garantili ürünleridir` politikasını net bir şekilde belirt.\n\n"
    "SENARYO VE CASE_TYPE SINIFLANDIRMASI:\n"
    "- exact_code_price_stock: Müşteri net parça kodu verip fiyat veya stok soruyor (Örn: \"MANN W 712/95 var mı, fiyatı nedir?\"). DİKKAT: Bu durumda replyDraft içinde ASLA şasi numarası (VIN) veya araç bilgisi isteme! Usta zaten kodu vermiştir.\n"
    "- exact_code_compatibility: Müşteri parça kodu verip \"Bu kod aracıma uyar mı?\" soruyor.\n"
    "- cross_reference: Müşteri farklı bir kodun veya markanın muadilini soruyor (Örn: \"C 35 154 FILTRON muadili nedir?\").\n"
    "- partial_code: Kod eksik veya belirsiz (Örn: \"712/95\").\n"
    "- vehicle_based_search: Parça kodu vermeden aracı için filtre istiyor (Örn: \"Clio 4 mazot filtresi\").\n"
    "- greeting: Selamlama, tanışma veya parça kodu/araç bilgisi içermeyen genel giriş mesajları (Örn: \"Selam\", \"Filtre var mı?\", \"Merhaba\", \"Kolay gelsin\").\n"
    "- non_product: İade, şikayet, ödeme sorunu, bayilik veya insan temsilci talebi. DİKKAT: 'Selam', 'merhaba', 'günaydın' gibi selamlaşma kelimeleri VE 'filtre var mi', 'fiyat nedir', 'neler var' gibi ürün sorguları birlikte geldiğinde BU DURUM greeting veya vehicle_based_search olabilir. 'non_product' SADECE açıkça şikayet, iade, geri ödeme, hasar, kırık, bayilik veya temsilci talebi içeren mesajlarda kullanılmalıdır.\n\n"
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


clear_batch_js = (
    "let currentInput = {};\n"
    "try {\n"
    "  currentInput = $input.item.json;\n"
    "} catch(e) {\n"
    "  console.error('[Finalize Batch] Girdi okunamadı:', e?.message || e);\n"
    "  throw new Error('Finalize Batch girdisi okunamadı');\n"
    "}\n"
    "let input = {};\n"
    "const lookupErrors = [];\n"
    "try {\n"
    "  input = Object.assign({}, $item(\"Parse AI Output\").$json, currentInput);\n"
    "} catch(e) {\n"
    "  lookupErrors.push('Parse AI Output: ' + (e?.message || e));\n"
    "}\n"
    "if (!input.senderNumber) {\n"
    "  try {\n"
    "    const commandInput = $item(\"Batch Collector\").$json;\n"
    "    if (commandInput?._action === 'command') return { json: Object.assign({}, commandInput, currentInput) };\n"
    "  } catch(e) {\n"
    "    lookupErrors.push('Batch Collector: ' + (e?.message || e));\n"
    "  }\n"
    "  try {\n"
    "    const idleInput = $item(\"Idle Timeout Check\").$json;\n"
    "    if (idleInput?._idleAlert === true) return { json: Object.assign({}, idleInput, currentInput) };\n"
    "  } catch(e) {\n"
    "    lookupErrors.push('Idle Timeout Check: ' + (e?.message || e));\n"
    "  }\n"
    "}\n"
    "if (!input.senderNumber) {\n"
    "  console.error('[Finalize Batch] Bağlam çözümlenemedi:', lookupErrors.join(' | '));\n"
    "  console.warn('[Finalize Batch] Uyari: senderNumber bulunamadi.'); return { json: currentInput };\n"
    "}\n"
    "const staticData = $getWorkflowStaticData('global');\n"
    "const senderNumber = String(input.senderNumber || '');\n"
    "const batchToken = String(input.batchToken || (senderNumber + '_' + (input.processingStartedAt || Date.now())));\n\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n"
    "if (input.pauseAutomation === true || input.action === 'handoff') {\n"
    "  staticData._manualModes[senderNumber] = true;\n"
    "}\n\n"
    "// Delivery Aggregation & Idempotency Protection\n"
    "if (!staticData._finalizedTokens) staticData._finalizedTokens = {};\n"
    "if (!staticData._deliveryLedger) staticData._deliveryLedger = {};\n"
    "const nowTs = Date.now();\n"
    "for (const k of Object.keys(staticData._finalizedTokens)) {\n"
    "  if (nowTs - staticData._finalizedTokens[k] > 600000) delete staticData._finalizedTokens[k];\n"
    "}\n"
    "for (const k of Object.keys(staticData._deliveryLedger)) {\n"
    "  if (nowTs - (staticData._deliveryLedger[k].createdAt || 0) > 600000) delete staticData._deliveryLedger[k];\n"
    "}\n\n"
    "if (staticData._finalizedTokens[batchToken]) {\n"
    "  return { json: input };\n"
    "}\n\n"
    "const completedChannel = String(input.completedChannel || '');\n"
    "if (staticData._deliveryLedger[batchToken]) {\n"
    "  const ledger = staticData._deliveryLedger[batchToken];\n"
    "  if (completedChannel && ledger.expected && ledger.expected[completedChannel] !== undefined) {\n"
    "    ledger.completed[completedChannel] = true;\n"
    "  }\n"
    "  const allCompleted = Object.keys(ledger.expected || {}).every(ch => !ledger.expected[ch] || ledger.completed[ch]);\n"
    "  if (!allCompleted) {\n"
    "    return { json: input };\n"
    "  }\n"
    "  delete staticData._deliveryLedger[batchToken];\n"
    "}\n\n"
    "staticData._finalizedTokens[batchToken] = nowTs;\n\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n\n"
    "// Handoff veya pauseAutomation tetiklendiyse müşteriyi manuel moda kilitliyoruz\n"
    "if (input.pauseAutomation === true || input.action === 'handoff') {\n"
    "  staticData._manualModes[senderNumber] = true;\n"
    "  staticData._manualModes = Object.assign({}, staticData._manualModes);\n"
    "  if (staticData._batches && staticData._batches[senderNumber]) {\n"
    "    const batch = staticData._batches[senderNumber];\n"
    "    // OUT-003 & STA-001: Handoff sırasında gelen yeni mesajları (pendingMessages) silme, koru veya yöneticinin bildirimine ekle\n"
    "    if (Array.isArray(batch.pendingMessages) && batch.pendingMessages.length > 0) {\n"
    "      const unread = batch.pendingMessages.map(m => m.text).join(' | ');\n"
    "      if (input.bildirim) input.bildirim += `\\n\\n⚡ Handoff Anında Bekleyen Mesajlar: ${unread}`;\n"
    "      batch.processingMessages = [];\n"
    "      batch.processing = false;\n"
    "      batch.processingToken = null;\n"
    "      batch.processingStartedAt = null;\n"
    "    } else {\n"
    "      delete staticData._batches[senderNumber];\n"
    "    }\n"
    "  }\n"
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
    "// ═══════════════════════════════════════════════════════════════\n"
    "// IDL-001: Yalnızca kesin yanıt beklenen koşullarda _lastReply kaydet\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "if (input.action === 'reply' && input.expectsReply === true && !input.pauseAutomation && senderNumber) {\n"
    "  if (!staticData._lastReply) staticData._lastReply = {};\n"
    "  staticData._lastReply[senderNumber] = Date.now();\n"
    "}\n\n"
    "return { json: input };"
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

# ── Channel Metadata Tagging JS (P1/P2 Requirement) ──
tag_succ_phone_a_js = 'const input = $input.first().json; return [{ json: { ...input, completedChannel: "phoneA" } }];'
tag_succ_phone_b_js = 'const input = $input.first().json; return [{ json: { ...input, completedChannel: "phoneB" } }];'
tag_succ_reply_js = 'const input = $input.first().json; return [{ json: { ...input, completedChannel: "customer" } }];'
tag_err_phone_a_js = 'const input = $input.first().json; return [{ json: { ...input, failedChannel: "Phone A Send (Yönetici A)", completedChannel: "phoneA" } }];'
tag_err_phone_b_js = 'const input = $input.first().json; return [{ json: { ...input, failedChannel: "Phone B Send (Yönetici B)", completedChannel: "phoneB" } }];'
tag_err_reply_js = 'const input = $input.first().json; return [{ json: { ...input, failedChannel: "Reply to Customer (Müşteri Cevap)", completedChannel: "customer" } }];'

nodes = [
    {
        "parameters": {
            "httpMethod": "POST", 
            "path": "evolution-webhook", 
            "responseMode": "onReceived", 
            "options": {},
            "authentication": "query",
            "queryAuth": "={{ $credentials.WebhookAuth.token }}"
        },
        "id": get_node_id("Webhook1"), 
        "name": "Webhook1",
        "type": "n8n-nodes-base.webhook", 
        "typeVersion": 1.1, 
        "position": [240, 640],
        "webhookId": "d4e5f6a7-b8c9-4d0e-8f1a-2b3c4d5e6f7a"
    },
    {
        "parameters": {
            "mode": "runOnceForAllItems",
            "jsCode": (
                "const staticData = $getWorkflowStaticData('global');\n"
                "const expectedSecret = staticData._webhookSecret || '';\n\n"
                "if (!expectedSecret) {\n"
                "    const input = $input.item.json;\n"
                "    return [{ json: input }];\n"
                "}\n\n"
                "const input = $input.first().json;\n"
                "const queryToken = input?.query?.token || '';\n"
                "const headerToken = input?.headers?.['x-webhook-secret'] || '';\n"
                "const bodySecret = input?.body?.secret || '';\n"
                "const providedSecret = queryToken || headerToken || bodySecret;\n"
                "if (providedSecret !== expectedSecret) {\n"
                "    throw new Error('Webhook authentication failed: Invalid secret');\n"
                "}\n\n"
                "return [{ json: input }];\n"
            )
        },
        "id": get_node_id("Webhook Auth Check"), "name": "Webhook Auth Check",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [388, 640]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [
                    {"id": "cond-allow", "leftValue": "={{ (!($json.body?.data?.key?.fromMe) && !['++', '--'].includes($json.body?.data?.message?.conversation || $json.body?.data?.message?.extendedTextMessage?.text || '')) || ($json.body?.data?.key?.fromMe && ['++', '--'].includes($json.body?.data?.message?.conversation || $json.body?.data?.message?.extendedTextMessage?.text || '')) }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}},
                    {"id": "cond-no-group", "leftValue": "={{ $json.body.data.key.remoteJid }}", "rightValue": "@g.us", "operator": {"type": "string", "operation": "notEndsWith"}},
                    {"id": "cond-no-broadcast", "leftValue": "={{ $json.body.data.key.remoteJid }}", "rightValue": "@broadcast", "operator": {"type": "string", "operation": "notEndsWith"}}
                ],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("fromMe Check"), "name": "fromMe Check",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [528, 640]
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": batch_collector_js},
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
        "parameters": {
            "method": "DELETE", "url": "https://evo.filtreoto.online/chat/deleteMessageForEveryone/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ id: $json.commandMessageId, fromMe: $json.commandFromMe === true, remoteJid: $json.commandRemoteJid, ...($json.commandParticipant ? { participant: $json.commandParticipant } : {}) }) }}",
            "options": {"timeout": 5000}
        },
        "id": get_node_id("Delete Command Message"), "name": "Delete Command Message",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1248, 1080],
        "retryOnFail": False, "maxTries": 1, "waitBetweenTries": 0, "onError": "continueRegularOutput"
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": store_context_js},
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
        "parameters": {"mode": "runOnceForAllItems", "jsCode": parse_ai_output_js},
        "id": get_node_id("Parse AI Output"), "name": "Parse AI Output",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1808, 624]
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": clear_batch_js},
        "id": get_node_id("Finalize Batch"), "name": "Finalize Batch",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2800, 640]
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
                {"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905052237182', text: $json.bildirim }) }}",
            "options": {"timeout": 30000, "batching": {"batch": {"batchSize": 1, "batchInterval": 100}}}
        },
        "id": get_node_id("Phone A Send"), "name": "Phone A Send",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2480, 416],
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000, "onError": "continueErrorOutput"
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905306056066', text: $json.bildirim }) }}",
            "options": {"timeout": 30000}
        },
        "id": get_node_id("Phone B Send"), "name": "Phone B Send",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2480, 624],
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000, "onError": "continueErrorOutput"
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: $json.senderNumber, text: $json.cevap }) }}",
            "options": {"timeout": 30000}
        },
        "id": get_node_id("Reply to Customer"), "name": "Reply to Customer",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2480, 864],
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000, "onError": "continueErrorOutput"
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905052237182', text: `🚨 SİSTEM HATASI (Dead-Letter)\n\n- Hedef/Müşteri: ${$json.senderNumber || $json.number || 'Bilinmiyor'}\n- Başarısız Kanal: ${$json.failedChannel || 'Bilinmeyen Kanal'}\n- Batch Token: ${$json.batchToken || 'Yok'}\n- Hata Detayı: ${JSON.stringify($json.error || $json.message || 'Evolution API HTTP Bağlantı/Timeout Hatası')}\n- Execution ID: ${$execution.id || 'Yok'}\n\nLütfen n8n panelinden ilgili execution kaydını kontrol edin.` }) }}",
            "options": {"timeout": 30000}
        },
        "id": get_node_id("Dead Letter Admin"), "name": "Dead Letter Admin",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2480, 1000]
    },
    {
        "parameters": {"rule": {"interval": [{"field": "seconds", "secondsInterval": 15}]}},
        "id": get_node_id("Schedule Trigger"), "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [240, 1104]
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": stale_batch_check_js},
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
        "parameters": {"mode": "runOnceForAllItems", "jsCode": idle_timeout_check_js},
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
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": tag_succ_phone_a_js},
        "id": get_node_id("Tag Success Phone A"), "name": "Tag Success Phone A",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2680, 500]
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": tag_succ_phone_b_js},
        "id": get_node_id("Tag Success Phone B"), "name": "Tag Success Phone B",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2680, 680]
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": tag_succ_reply_js},
        "id": get_node_id("Tag Success Reply"), "name": "Tag Success Reply",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2680, 860]
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": tag_err_phone_a_js},
        "id": get_node_id("Tag Err Phone A"), "name": "Tag Err Phone A",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2580, 580]
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": tag_err_phone_b_js},
        "id": get_node_id("Tag Err Phone B"), "name": "Tag Err Phone B",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2580, 760]
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": tag_err_reply_js},
        "id": get_node_id("Tag Err Reply"), "name": "Tag Err Reply",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2580, 940]
    }
]
# ── Connections ──
connections = {
    "Webhook1": {"main": [[{"node": "Webhook Auth Check", "type": "main", "index": 0}]]},
    "Webhook Auth Check": {"main": [[{"node": "fromMe Check", "type": "main", "index": 0}]]},
    "fromMe Check": {"main": [[{"node": "Batch Collector", "type": "main", "index": 0}], []]},
    "Batch Collector": {"main": [[{"node": "Should Process?", "type": "main", "index": 0}, {"node": "Is Command?", "type": "main", "index": 0}]]},
    "Should Process?": {"main": [[{"node": "Store Context", "type": "main", "index": 0}], []]},
    "Is Command?": {"main": [[{"node": "Delete Command Message", "type": "main", "index": 0}, {"node": "Phone A Send", "type": "main", "index": 0}, {"node": "Phone B Send", "type": "main", "index": 0}], []]},
    "Delete Command Message": {"main": [[]]},
    "Store Context": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
    "AI Agent": {"main": [[{"node": "Parse AI Output", "type": "main", "index": 0}]]},
      "Parse AI Output": {"main": [[{"node": "Should Notify Admins?", "type": "main", "index": 0}, {"node": "Should Reply Customer?", "type": "main", "index": 0}]]},
      "Finalize Batch": {"main": [[]]},
    "Should Notify Admins?": {"main": [[{"node": "Phone A Send", "type": "main", "index": 0}, {"node": "Phone B Send", "type": "main", "index": 0}], [{"node": "Finalize Batch", "type": "main", "index": 0}]]},
    "Should Reply Customer?": {"main": [[{"node": "Reply to Customer", "type": "main", "index": 0}], [{"node": "Finalize Batch", "type": "main", "index": 0}]]},
      "Phone A Send": {"main": [[{"node": "Tag Success Phone A", "type": "main", "index": 0}], [{"node": "Tag Err Phone A", "type": "main", "index": 0}]]},
      "Phone B Send": {"main": [[{"node": "Tag Success Phone B", "type": "main", "index": 0}], [{"node": "Tag Err Phone B", "type": "main", "index": 0}]]},
      "Reply to Customer": {"main": [[{"node": "Tag Success Reply", "type": "main", "index": 0}], [{"node": "Tag Err Reply", "type": "main", "index": 0}]]},
      "Tag Success Phone A": {"main": [[{"node": "Finalize Batch", "type": "main", "index": 0}]]},
      "Tag Success Phone B": {"main": [[{"node": "Finalize Batch", "type": "main", "index": 0}]]},
      "Tag Success Reply": {"main": [[{"node": "Finalize Batch", "type": "main", "index": 0}]]},
      "Tag Err Phone A": {"main": [[{"node": "Dead Letter Admin", "type": "main", "index": 0}, {"node": "Finalize Batch", "type": "main", "index": 0}]]},
      "Tag Err Phone B": {"main": [[{"node": "Dead Letter Admin", "type": "main", "index": 0}, {"node": "Finalize Batch", "type": "main", "index": 0}]]},
      "Tag Err Reply": {"main": [[{"node": "Dead Letter Admin", "type": "main", "index": 0}, {"node": "Finalize Batch", "type": "main", "index": 0}]]},
      "Dead Letter Admin": {"main": [[]]},
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
except FileNotFoundError:
    wf = {}
except json.JSONDecodeError as exc:
    raise RuntimeError(f"BUILD ABORTED: workflow.json geçersiz JSON: {exc}") from exc
except OSError as exc:
    raise RuntimeError(f"BUILD ABORTED: workflow.json okunamadı: {exc}") from exc

wf["name"] = "WhatsApp AI - v12.5 Enterprise"
wf["nodes"] = nodes
wf["connections"] = connections
wf["settings"] = {"executionOrder": "v1", "saveDataSuccessExecution": "none", "saveExecutionProgress": False, "saveManualExecutions": True}
if "staticData" not in wf or not wf["staticData"]:
    wf["staticData"] = {
        "node:Schedule Trigger": {"recurrenceRules": []},
        "global": {
            "_batches": {},
            "_webhookSecret": "={{ $env.N8N_WEBHOOK_SECRET }}"
        }
    }
wf["meta"] = {"templateCredsSetupCompleted": True}
wf["pinData"] = {}

with open("workflow.json", "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)

print(f"workflow.json v12.5 Enterprise generated: {len(nodes)} nodes, {len(connections)} connection sources")

# ── Automated JS Syntax Verification (P1 Requirement) ──
import subprocess
import os

print("Running automated node --check syntax verification on all JS nodes...")
syntax_failed = False
for node in wf.get("nodes", []):
    if "jsCode" in node.get("parameters", {}):
        code = node["parameters"]["jsCode"]
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as jf:
            jf.write("(async () => {\n")
            jf.write(code)
            jf.write("\n})();\n")
            tmp_js = jf.name
        res = subprocess.run(["node", "--check", tmp_js], capture_output=True, text=True)
        if os.path.exists(tmp_js):
            os.remove(tmp_js)
        if res.returncode != 0:
            print(f"[FAIL] SYNTAX ERROR in node [{node['name']}]:\n{res.stderr.strip()}")
            syntax_failed = True
        else:
            print(f"[PASS] Syntax OK [{node['name']}]")

if syntax_failed:
    raise RuntimeError("BUILD ABORTED: JavaScript syntax check FAILED on one or more nodes!")
