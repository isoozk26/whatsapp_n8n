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

parse_ai_output_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const currentInput = $input.item.json;\n"
    "const rawAiOutput = currentInput?.output || currentInput?.aiResult || '';\n"
            "const aiOutput = typeof rawAiOutput === 'string' ? rawAiOutput : JSON.stringify(rawAiOutput);\n\n"
    "let senderNumber = '';\n"
    "let senderName = '';\n"
    "let allMessagesText = '';\n"
    "let batchToken = '';\n"
    "let detectedCodes = [];\n"
    "try {\n"
    "  const sc = $('Store Context').item.json;\n"
    "  senderNumber = String(sc.senderNumber || '');\n"
    "  senderName = String(sc.senderName || senderNumber || 'Bilinmeyen müşteri');\n"
    "  allMessagesText = String(sc.allMessagesText || '');\n"
    "  batchToken = String(sc.batchToken || '');\n"
    "  if (Array.isArray(sc.detectedCodes)) detectedCodes = sc.detectedCodes;\n"
    "} catch(e) {\n"
    "  console.error('[Parse AI Output] Store Context okunamadı:', e?.message || e);\n"
    "  throw new Error('Parse AI Output gerekli Store Context verisine ulaşamadı');\n"
    "}\n\n"
    "if (!staticData._unclearCounts) staticData._unclearCounts = {};\n"
    "if (!staticData._batches) staticData._batches = {};\n"
    "if (!staticData._adminNotifications) staticData._adminNotifications = {};\n\n"
    "const batch = staticData._batches[senderNumber];\n"
    "const validClaim = Boolean(batch && batch.processing === true && batch.processingToken === batchToken);\n\n"
    "if (!validClaim && senderNumber) {\n"
    "  return { json: {\n"
    "    senderNumber, senderName, batchToken, action: 'ignore', intent: 'other', caseType: 'other',\n"
    "    cevap: '', missingFields: [], confidence: 0, handoffReason: 'Geçersiz veya süresi dolmuş işlem yutuldu',\n"
    "    notifyAdmins: false, validClaim: false, bildirim: ''\n"
    "  }};\n"
    "}\n\n"
    "let parsed = null;\n"
    "if (typeof rawAiOutput === 'object' && rawAiOutput !== null) {\n"
    "  parsed = rawAiOutput;\n"
    "} else {\n"
    "  try {\n"
    "    const cleaned = aiOutput.replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```$/i, '').trim();\n"
    "    parsed = JSON.parse(cleaned);\n"
    "  } catch (e1) {\n"
    "    try {\n"
    "      const match = aiOutput.match(/\\{[\\s\\S]*\\}/);\n"
    "      if (match) parsed = JSON.parse(match[0]);\n"
    "    } catch(e2) {\n"
    "      console.error('[Parse AI Output] AI JSON ayrıştırılamadı:', e1?.message || e1, e2?.message || e2);\n"
    "    }\n"
    "  }\n"
    "}\n\n"
    "if (!parsed) {\n"
    "  return { json: {\n"
    "    senderNumber, senderName, batchToken, action: 'handoff', intent: 'unclear', caseType: 'unclear',\n"
    "    cevap: 'Talebinizi ilgili ekibimize aktarıyorum. Yetkilimiz sizinle ilgilenecektir.',\n"
    "    missingFields: [], confidence: 0, handoffReason: 'AI JSON ayrıştırma hatası',\n"
    "    notifyAdmins: true, validClaim: true, pauseAutomation: true,\n"
    "    bildirim: `⚠️ AI ÇIKTISI AYRIŞTIRILAMADI\\nMüşteri: ${senderName} (${senderNumber})\\nMesaj: ${allMessagesText}`\n"
    "  }};\n"
    "}\n\n"
    "const intent = String(parsed.intent || 'other').trim();\n"
    "let caseType = String(parsed.caseType || intent || 'other').trim();\n"
    "const entities = parsed.entities || {};\n"
    "let replyDraft = String(parsed.replyDraft || parsed.reply || parsed.cevap || '').trim();\n"
    "// Boş cevap koruması (Fallback)\n"
    "if (!replyDraft || replyDraft.trim() === '') {\n"
    "  if (caseType === 'exact_code_price_stock' || caseType === 'cross_reference') {\n"
    "    replyDraft = 'Talebiniz alınmıştır. Güncel stok ve fiyat kontrolü yapılarak size bilgi verilecektir.';\n"
    "  } else if (caseType === 'exact_code_compatibility' || caseType === 'vehicle_based_search') {\n"
    "    replyDraft = 'Araç uyumluluk kontrolünüz ilgili birimimize iletilmiştir, yetkilimiz tarafından bilgilendirileceksiniz.';\n"
    "  } else if (caseType === 'partial_code') {\n"
    "    replyDraft = 'İletmiş olduğunuz kod tam olarak anlaşılamadı veya eksik. Filtre kodunun tamamını veya aracınızın detaylarını paylaşabilir misiniz?';\n"
    "  } else if (caseType === 'greeting') {\n"
    "    replyDraft = 'Merhaba! Size nasıl yardımcı olabilirim? (Lütfen filtre kodunuzu veya aracınızın motor hacmi ve beygir gücü/şasi numarasını belirtin)';\n"
    "  } else if (caseType === 'unclear') {\n"
    "    replyDraft = 'İfadenizi tam anlayamadım, ilgili uzmanımıza aktarıyorum.';\n"
    "  } else {\n"
    "    replyDraft = 'Talebiniz müşteri temsilcimize aktarılmıştır.';\n"
    "  }\n"
    "}\n"
    "const missingFields = Array.isArray(parsed.missingFields) ? parsed.missingFields.slice(0, 10) : [];\n"
    "const verification = parsed.verification || {};\n\n"
    "// P0-1: Quantity Provenance\n"
    "if (entities.quantity && entities.quantity !== 'Belirtilmedi') {\n"
    "  const nums = String(entities.quantity).match(/\\d+/g);\n"
    "  if (nums && nums.length > 0) {\n"
    "    const num = nums[0];\n"
    "    const qtyRegex = new RegExp(`\\\\b${num}\\\\s*(?:adet|tane|pcs|x)|(?:x)\\\\s*${num}\\\\b`, \'i\');\n"
    "    const textHasNumContext = qtyRegex.test(allMessagesText);\n"
    "    if (!textHasNumContext) entities.quantity = \'Belirtilmedi\';\n"
    "  } else {\n"
    "  }\n"
    "}\n\n"
    "// P0-2: Granular Vehicle Provenance (brand/model/year/engine/vin)\n"
    "if (Array.isArray(entities.vehicles)) {\n"
    "  entities.vehicles = entities.vehicles.map(v => {\n"
    "    const textLower = allMessagesText.toLowerCase();\n"
    "    if (typeof v === 'object' && v) {\n"
    "      if (v.brand && !textLower.includes(String(v.brand).toLowerCase())) v.brand = null;\n"
    "      if (v.model && !textLower.includes(String(v.model).toLowerCase())) v.model = null;\n"
    "      if (v.year && !allMessagesText.includes(String(v.year))) v.year = null;\n"
    "      if (v.engine && !textLower.includes(String(v.engine).toLowerCase())) v.engine = null;\n"
    "      if (v.horsePower && !textLower.includes(String(v.horsePower).toLowerCase())) v.horsePower = null;\n"
    "      if (v.vin && !textLower.includes(String(v.vin).toLowerCase())) v.vin = null;\n"
    "      if (!v.brand && !v.model && !v.year && !v.engine && !v.vin && !v.raw) return null;\n"
    "      if (v.raw) {\n"
    "        const yearMatch = String(v.raw).match(/\\b(19\\d\\d|20\\d\\d)\\b/);\n"
    "        if (yearMatch && !allMessagesText.includes(yearMatch[1])) v.raw = null;\n"
    "        const rawWords = String(v.raw).toLowerCase().replace(/[^a-z0-9]/g, ' ').split(/\\s+/).filter(w => w.length > 2);\n"
    "        if (v.raw && rawWords.length > 0 && !rawWords.every(w => textLower.includes(w))) v.raw = null;\n"
    "      }\n"
    "      return v;\n"
    "    } else {\n"
    "      let str = String(v);\n"
    "      const yearMatch = str.match(/\\b(19\\d\\d|20\\d\\d)\\b/);\n"
    "      if (yearMatch && !allMessagesText.includes(yearMatch[1])) return null;\n"
    "      const engineMatch = str.match(/\\b(\\d\\.\\d)\\b/);\n"
    "      if (engineMatch && !allMessagesText.includes(engineMatch[1])) return null;\n"
    "      const words = str.toLowerCase().replace(/[^a-z0-9]/g, ' ').split(/\\s+/).filter(w => w.length > 2);\n"
    "      if (words.length > 0 && !words.every(w => textLower.includes(w))) return null;\n"
    "      return v;\n"
    "    }\n"
    "  }).filter(Boolean);\n"
    "}\n\n"
    "// P1-5: Preferred Brands\n"
    "const knownBrands = ['MANN', 'BOSCH', 'FILTRON', 'UFI', 'HENGST', 'PURFLUX', 'MAHLE', 'FILTORQ'];\n"
    "const textUpper = allMessagesText.toUpperCase();\n"
    "const detectedBrands = knownBrands.filter(b => textUpper.includes(b));\n"
    "if (detectedBrands.length > 0) {\n"
    "  let existing = Array.isArray(entities.preferredBrands) ? entities.preferredBrands : [];\n"
    "  entities.preferredBrands = [...new Set([...existing.map(x=>String(x).toUpperCase()), ...detectedBrands])];\n"
    "}\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// SCH-001: CASE_TYPE ALLOWLIST & SCHEMA ENFORCEMENT\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "const validCaseTypes = [\n"
    "  'exact_code_price_stock',\n"
    "  'exact_code_compatibility',\n"
    "  'cross_reference',\n"
    "  'partial_code',\n"
    "  'vehicle_based_search',\n"
    "  'non_product',\n"
    "  'unclear',\n"
    "  'greeting'\n"
    "];\n\n"
    "let isSchemaViolation = false;\n"
    "if (!validCaseTypes.includes(caseType)) {\n"
    "  isSchemaViolation = true;\n"
    "  caseType = 'unclear';\n"
    "}\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// DÜZELTME 1: CONFİDENCE — İKİ TİP DESTEĞİ (number + object)\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "let confidenceValue = 0;\n"
    "const rawConfidence = parsed.confidence;\n"
    "if (typeof rawConfidence === 'number' && Number.isFinite(rawConfidence)) {\n"
    "  confidenceValue = rawConfidence;\n"
    "} else if (typeof rawConfidence === 'object' && rawConfidence !== null) {\n"
    "  const vals = [\n"
    "    Number(rawConfidence.intent || 0),\n"
    "    Number(rawConfidence.caseType || 0),\n"
    "    Number(rawConfidence.entityExtraction || 0)\n"
    "  ].filter(v => Number.isFinite(v));\n"
    "  confidenceValue = vals.length > 0 ? Math.min(...vals) : 0;\n"
    "}\n"
    "confidenceValue = Math.max(0, Math.min(1, confidenceValue));\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// GRD-002: VERIFICATION HARD-RESET (No External Verification Node)\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "const hasExternalVerification = Boolean(currentInput?.externalVerificationVerified === true);\n"
    "if (!hasExternalVerification) {\n"
    "  verification.priceVerified = false;\n"
    "  verification.stockVerified = false;\n"
    "  verification.compatibilityVerified = false;\n"
    "  verification.catalogVerified = false;\n"
    "  verification.dataSource = 'unverified_ai_output';\n"
    "}\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// GRD-003: LAYER 2 GUARDRAIL (DOĞRUDAN UYUMLULUK VE STOK GARANTİSİ INTERCEPTOR)\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "let guardrailTriggered = false;\n"
    "let triggeredRule = '';\n\n"
    "const PRICE_PATTERN = /(?:₺\\s*\\d+(?:[\\.,]\\d+)?|\\d+(?:[\\.,]\\d+)?\\s*(?:TL|₺|TRY|Lira)|(?:fiyat[ıi]?|ücret|bedel|tutar)\\s*[:=]?\\s*\\d{2,}|(?:yüz|bin|milyon)\\s+(?:lira|tl))/i;\n"
    "const COMPAT_GUARANTEE = /(?:(?:kesin(?:likle)?|garanti|tam(?:amen)?|net|birebir|%100|%99)\\s*(?:uy(?:ar|umlu|um|gundur)?|olur|oturur|tak[ıi]l[ıi]r|geçer)|(?:ara(?:c|ç|c[ıi]n[ıi]z)a?|motor(?:a|u|unuza)?|model(?:e|inize)?)\\s+(?:tam\\s+)?(?:uyar|uygundur|uyumludur|olur)|\\b(?:uygundur|uyumludur)\\b)/i;\n"
    "const STOCK_GUARANTEE = /(?:stok(?:ta|larımızda|umuzda|larda)?|elimizde|depo(?:muz)?da)\\s+(?:mevcut(?:tur|dur)?|var(?:dır)?|bulun(?:uyor|maktad[ıi]r)|uygun(?:dur)?|mevcuttur)/i;\n"
    "const BANNED_PHRASES = [\n"
    "  'stokta var',\n"
    "  'stoklarımızda mevcut',\n"
    "  'elimizde mevcut',\n"
    "  'kesin uyar',\n"
    "  'uyumludur',\n"
    "  'uygundur',\n"
    "  'aracınıza uyar',\n"
    "  'aracınızla uyumludur',\n"
    "  'aracınız için uygundur',\n"
    "  'birebir muadilidir',\n"
    "  'yerine kullanabilirsiniz',\n"
    "  'garanti uyar',\n"
    "  'garanti uygundur',\n"
    "  'mevcut görünüyor',\n"
    "  'sorunsuz kullanabilirsiniz',\n"
    "  'birebir karşılığıdır',\n"
    "  'tam karşılığıdır',\n"
    "  'direkt takılır',\n"
    "  'rahatlıkla kullanabilirsiniz'\n"
    "];\n\n"
    "const UNSAFE_CONTENT = /(?:https?:\\/\\/|www\\.)[^\\s]+|şifre|kredi\\s?kart|\\bcvv\\b|\\botp\\b/i;\n"
    "if (UNSAFE_CONTENT.test(replyDraft)) {\n"
    "  guardrailTriggered = true;\n"
    "  triggeredRule = 'Güvenli olmayan bağlantı veya hassas veri talebi';\n"
    "} else if (verification.priceVerified !== true && PRICE_PATTERN.test(replyDraft)) {\n"
    "  guardrailTriggered = true;\n"
    "  triggeredRule = 'Doğrulanmamış rakamsal fiyat/TL halüsinasyonu';\n"
    "} else if (verification.stockVerified !== true || verification.compatibilityVerified !== true) {\n"
    "  if (COMPAT_GUARANTEE.test(replyDraft) || STOCK_GUARANTEE.test(replyDraft)) {\n"
    "    guardrailTriggered = true;\n"
    "    triggeredRule = 'Yasaklı stok/uyumluluk garantisi';\n"
    "  } else {\n"
    "    const replyLower = replyDraft.toLocaleLowerCase('tr-TR');\n"
    "    for (const phrase of BANNED_PHRASES) {\n"
    "      if (replyLower.includes(phrase.toLocaleLowerCase('tr-TR'))) {\n"
    "        guardrailTriggered = true;\n"
    "        triggeredRule = `Yasaklı stok/uyumluluk garantisi ('${phrase}')`;\n"
    "        break;\n"
    "      }\n"
    "    }\n"
    "  }\n"
    "}\n\n"
    "if (guardrailTriggered) {\n"
    "  replyDraft = 'Ürünün güncel stok, fiyat ve teknik uygunluk bilgisi yetkilimiz tarafından kontrol edilerek size iletilecektir.';\n"
    "}\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// PRV-001: PROVENANCE CHECK (Katalog/Mesaj Dışı Parça Kodu Halüsinasyon Kontrolü)\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "const extractedCodeItems = Array.isArray(entities.productCodes) ? entities.productCodes : [];\n"
    "if (extractedCodeItems.length > 0) {\n"
    "  const rawCodes = extractedCodeItems.map(c => typeof c === 'object' ? (c.code || c.raw) : c).filter(Boolean);\n"
    "  const sorted = [...new Set(rawCodes)].sort((a, b) => String(b).length - String(a).length);\n"
    "  const deduped = [];\n"
    "  for (const c of sorted) {\n"
    "    if (!deduped.some(selected => String(selected).includes(String(c)))) deduped.push(c);\n"
    "  }\n"
    "  entities.productCodes = deduped;\n"
    "}\n"
    "let provenanceViolation = false;\n"
    "let unverifiedCode = '';\n\n"
    "if (extractedCodeItems.length > 0 && intent !== 'greeting' && caseType !== 'greeting') {\n"
    "  const normalizeForMatch = (str) => String(str || '').replace(/[\\s\\-\\/\\._\\\\]+/g, '').toLocaleLowerCase('tr-TR');\n"
    "  const normAllMessages = normalizeForMatch(allMessagesText);\n"
    "  const normDetected = (Array.isArray(detectedCodes) ? detectedCodes : []).map(c => normalizeForMatch(c));\n\n"
    "  for (const item of extractedCodeItems) {\n"
    "    const rawVal = typeof item === 'object' && item !== null ? String(item.raw || '') : String(item || '');\n"
    "    const codeVal = typeof item === 'object' && item !== null ? String(item.code || '') : String(item || '');\n\n"
    "    const candidates = [rawVal, codeVal].filter(s => s && s.trim().length >= 3);\n"
    "    if (candidates.length === 0) continue;\n\n"
    "    let isProven = false;\n"
    "    for (const cand of candidates) {\n"
    "      const normCand = normalizeForMatch(cand);\n"
    "      if (!normCand || normCand.length < 3) continue;\n\n"
    "      if (allMessagesText.toLocaleLowerCase('tr-TR').includes(cand.toLocaleLowerCase('tr-TR')) ||\n"
    "          normAllMessages.includes(normCand)) {\n"
    "        isProven = true;\n"
    "        break;\n"
    "      }\n\n"
    "      if (normDetected.some(d => d.includes(normCand) || normCand.includes(d))) {\n"
    "        isProven = true;\n"
    "        break;\n"
    "      }\n"
    "    }\n\n"
    "    if (!isProven) {\n"
    "      provenanceViolation = true;\n"
    "      unverifiedCode = candidates[0] || 'Bilinmeyen Kod';\n"
    "      break;\n"
    "    }\n"
    "  }\n"
    "}\n\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// POL-003: ARAÇ BİLGİSİ TAM OLMA (COMPLETENESS) KONTROL FONKSİYONU\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "function isVehicleComplete(vehicles) {\n"
    "  if (!Array.isArray(vehicles) || vehicles.length === 0) return false;\n"
    "  const vinStringMatch = /\\b[A-HJ-NPR-Z0-9]{17}\\b/i;\n"
    "  const engineRegex = /(?:\\b\\d+[\\.,]\\d+\\s*(?:td[iı]|ts[iı]|cdti|hd[iı]|tdci|mjet|tfsi|vvt-?i|l|lt|cc)?\\b|\\b\\d+\\s*(?:hp|bg|ps|kw|cc)\\b|\\b(?:td[iı]|ts[iı]|cdti|hd[iı]|tdci|mjet|tfsi)\\b)/i;\n\n"
    "  for (const v of vehicles) {\n"
    "    if (typeof v === 'string') {\n"
    "      const trimmed = v.trim();\n"
    "      if (vinStringMatch.test(trimmed)) return true;\n"
    "      const hasYear = /\\b(?:19|20)\\d{2}\\b/.test(trimmed);\n"
    "      const hasEngine = engineRegex.test(trimmed);\n"
    "      const words = trimmed.split(/\\s+/).filter(Boolean);\n"
    "      if (hasYear && hasEngine && words.length >= 4) return true;\n"
    "    } else if (typeof v === 'object' && v !== null) {\n"
    "      const vin = String(v.vin || v.chassis || v.sasi || '').trim();\n"
    "      if (vin.length === 17 || vinStringMatch.test(vin)) return true;\n"
    "      const fullObjStr = Object.values(v).join(' ');\n"
    "      if (vinStringMatch.test(fullObjStr)) return true;\n"
    "      const brand = String(v.brand || v.marka || '').trim();\n"
    "      const model = String(v.model || '').trim();\n"
    "      const year = String(v.year || v.yil || '').trim();\n"
    "      const engine = String(v.engine || v.motor || v.engineCode || v.motorKodu || v.hp || v.power || v.cc || v.spec || '').trim();\n"
    "      const hasBrandModelYear = Boolean(brand && model && year && /\\d{4}/.test(year));\n"
    "      const hasEngineSpec = Boolean(engine) || engineRegex.test(fullObjStr);\n"
    "      if (hasBrandModelYear && hasEngineSpec) return true;\n"
    "    }\n"
    "  }\n"
    "  return false;\n"
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
    "if (isSchemaViolation) {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = true;\n"
    "  action = 'handoff';\n"
    "  handoffReason = `Şema İhlali: Tanımsız/Uydurma Case Type engellendi ('${String(parsed.caseType || 'boş')}' -> 'unclear')`;\n"
    "  replyDraft = 'Talebinizi doğru yönlendirebilmek için ilgili ekibimize aktarıyorum. Yetkilimiz sizinle ilgilenecektir.';\n"
    "} else if (provenanceViolation) {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = true;\n"
    "  action = 'handoff';\n"
    "  handoffReason = `Katalog/Mesaj dışı parça kodu uydurma şüphesi (Provenance: '${unverifiedCode}')`;\n"
    "  replyDraft = 'Parça kodunuzu ve araç uyumluluğunu netleştirmek üzere talebinizi yetkilimize aktarıyorum.';\n"
    "  if (Array.isArray(entities.productCodes)) {\n"
    "    entities.productCodes = entities.productCodes.filter(c => {\n"
    "      const v = typeof c === 'object' && c !== null ? String(c.raw || c.code || '') : String(c || '');\n"
    "      return !v.includes(unverifiedCode) && !unverifiedCode.includes(v);\n"
    "    });\n"
    "  }\n"
    "} else if (confidenceValue < 0.55 && intent !== 'greeting' && intent !== 'unclear') {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = true;\n"
    "  action = 'handoff';\n"
    "  handoffReason = handoffReason || `Düşük güven skoru (${confidenceValue.toFixed(2)})`;\n"
    "  replyDraft = 'Talebinizi ilgili ekibimize aktarıyorum. Yetkilimiz sizinle ilgilenecektir.';\n"
    "} else if (guardrailTriggered) {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = false;\n"
    "} else if (caseType === 'exact_code_price_stock') {\n"
    "  requiresHumanAction = true;\n"
    "  notifyAdmin = true;\n"
    "  pauseAutomation = false;\n"
    "  askVehicleInfo = false; // KESİNLİKLE ŞASİ İSTEME!\n"
    "  const codesText = (entities.productCodes && entities.productCodes.length > 0) ? entities.productCodes.map(c => typeof c === 'object' ? (c.brand ? `${c.brand} ${c.code}` : (c.code || c.raw)) : c).join(', ') : 'İlettiğiniz ürün(ler)';\n"
    "  const miktarText = (!entities.quantity || String(entities.quantity).toLowerCase() === 'belirtilmedi') ? '' : `${entities.quantity} `;\n"
    "  replyDraft = `Talebiniz alındı.\\nStok ve net fiyat bilgisi en geç 5 dakika içinde paylaşılacaktır.`;\n"
    "} else if (caseType === 'exact_code_compatibility') {\n"
    "  if (!isVehicleComplete(entities.vehicles)) {\n"
    "    requiresHumanAction = false;\n"
    "    notifyAdmin = false;\n"
    "    pauseAutomation = false;\n"
    "    askVehicleInfo = true;\n"
    "    action = 'reply';\n"
    "    replyDraft = 'Araç uyumluluğunun kesin tespiti için lütfen aracınızın motor hacmini (örn: 1.6 TDI) ve beygir gücünü (veya şasi numarasını) belirtebilir misiniz?';\n"
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
    "  const sourceCode = (entities.productCodes && entities.productCodes.length > 0) ? (entities.productCodes[0].code || entities.productCodes[0].raw || entities.productCodes[0]) : 'Belirtilen';\n"
    "  const prefBrands = (entities.preferredBrands && entities.preferredBrands.length > 0) ? entities.preferredBrands.join(' veya ') : 'muadil';\n"
    "  replyDraft = `${sourceCode} kodu için ${prefBrands} talebinizi aldım. Yanlış parça yönlendirmemek için muadil kodu üretici kataloğundan teyit ederek paylaşacağız. Yetkilimiz kontrol sonrası size dönüş yapacaktır.`;\n"
    "} else if (caseType === 'partial_code') {\n"
    "  requiresHumanAction = false;\n"
    "  notifyAdmin = false;\n"
    "  pauseAutomation = false;\n"
    "} else if (caseType === 'vehicle_based_search') {\n"
    "  if (!isVehicleComplete(entities.vehicles)) {\n"
    "    requiresHumanAction = false;\n"
    "    notifyAdmin = false;\n"
    "    pauseAutomation = false;\n"
    "    askVehicleInfo = true;\n"
    "    action = 'reply';\n"
    "    replyDraft = 'Araç uyumluluğunun kesin tespiti için lütfen aracınızın motor hacmini (örn: 1.6 TDI) ve beygir gücünü (veya şasi numarasını) belirtebilir misiniz?';\n"
    "  } else {\n"
    "    requiresHumanAction = true;\n"
    "    notifyAdmin = true;\n"
    "    pauseAutomation = false;\n"
    "  }\n"
    "} else if (caseType === 'non_product' || intent === 'return_complaint' || intent === 'wholesale') {\n"
    "  // Ek doğrulama: Mesaj gerçekten şikayet/iade/içeriyor mu?\n"
    "  const complaintKeywords = ['şikayet', 'iade', 'geri', 'para iadesi', 'bozuk', 'hasarlı', 'kırık', 'yanlış', 'eksik', 'sorunlu', 'memnun değil', 'bayilik', 'temsilci'];\n"
    "  const hasComplaintKeyword = complaintKeywords.some(kw => allMessagesText.toLowerCase().includes(kw));\n"
    "  if (!hasComplaintKeyword) {\n"
    "    caseType = 'unclear';\n"
    "    action = 'reply';\n"
    "    notifyAdmin = false;\n"
    "    pauseAutomation = false;\n"
    "    requiresHumanAction = false;\n"
    "    replyDraft = 'Hangi konuda yardımcı olabilirim? Filtre mi arıyorsunuz, yoksa başka bir talebiniz mi var?';\n"
    "    handoffReason = '';\n"
    "  } else {\n"
    "    requiresHumanAction = true;\n"
    "    notifyAdmin = true;\n"
    "    pauseAutomation = true;\n"
    "    action = 'handoff';\n"
    "    handoffReason = `Özel durum veya temsilci talebi (${intent})`;\n"
    "  }\n"
    "} else if (caseType === 'unclear') {\n"
    "  staticData._unclearCounts[senderNumber] = Number(staticData._unclearCounts[senderNumber] || 0) + 1;\n"
    "  if (staticData._unclearCounts[senderNumber] >= 2) {\n"
    "    requiresHumanAction = true;\n"
    "    notifyAdmin = true;\n"
    "    pauseAutomation = true;\n"
    "    action = 'handoff';\n"
    "    handoffReason = 'Talep 2 kez üst üste anlaşılamadı';\n"
    "    replyDraft = 'Talebinizi doğru yönlendirebilmek için ilgili ekibimize aktarıyorum. Yetkilimiz sizinle ilgilenecektir.';\n"
    "  }\n"
    "} else if (caseType === 'greeting') {\n"
    "  requiresHumanAction = false;\n"
    "  notifyAdmin = false;\n"
    "  pauseAutomation = false;\n"
    "}\n\n"
    "if (caseType !== 'unclear' && !isSchemaViolation) delete staticData._unclearCounts[senderNumber];\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "// SPAM KORUMASI, COOLDOWN VE GÜNCELLEME BİLDİRİMİ\n"
    "// ═══════════════════════════════════════════════════════════════\n"
    "const now = Date.now();\n"
    "const lastNotif = staticData._adminNotifications[senderNumber];\n"
    "let isUpdate = false;\n"
    "let shouldNotifyAdmin = notifyAdmin;\n\n"
    "const notifKeys = Object.keys(staticData._adminNotifications);\n"
    "if (notifKeys.length > 500) {\n"
    "  const sorted = notifKeys.sort((a, b) =>\n"
    "    (staticData._adminNotifications[a].timestamp || 0) -\n"
    "    (staticData._adminNotifications[b].timestamp || 0)\n"
    "  );\n"
    "  sorted.slice(0, sorted.length - 300).forEach(k => delete staticData._adminNotifications[k]);\n"
    "}\n\n"
    "const currentCodes = Array.isArray(entities.productCodes) ? entities.productCodes.map(c => typeof c === 'object' ? c.code || c.raw : c).filter(Boolean) : [];\n"
    "const currentVehicles = Array.isArray(entities.vehicles) ? entities.vehicles.map(v => typeof v === 'object' ? `${v.brand||\'\'} ${v.model||\'\'} ${v.year||\'\'} ${v.engine||\'\'}`.trim() : String(v)).filter(Boolean) : [];\n"
    "const currentBrands = Array.isArray(entities.preferredBrands) ? entities.preferredBrands : [];\n"
    "const quantity = String(entities.quantity || 'Belirtilmedi');\n\n"
    "if (notifyAdmin && lastNotif && (now - Number(lastNotif.timestamp) < 3 * 60 * 1000)) {\n"
    "  const oldCodes = lastNotif.codes || [];\n"
    "  const oldVehicles = lastNotif.vehicles || [];\n"
    "  const oldBrands = lastNotif.brands || [];\n"
    "  const addedCodes = currentCodes.filter(c => !oldCodes.includes(c));\n"
    "  const addedVehicles = currentVehicles.filter(v => !oldVehicles.includes(v));\n"
    "  const addedBrands = currentBrands.filter(b => !oldBrands.includes(b));\n"
    "  const qtyChanged = lastNotif.quantity !== quantity && quantity !== 'Belirtilmedi';\n"
    "  if (addedCodes.length > 0 || addedVehicles.length > 0 || addedBrands.length > 0 || qtyChanged || caseType !== lastNotif.caseType) {\n"
    "    isUpdate = true;\n"
    "    shouldNotifyAdmin = true;\n"
    "  } else {\n"
    "    shouldNotifyAdmin = false;\n"
    "  }\n"
    "}\n\n"
    "let headerTitle = '';\n"
    "let yetkiliAksiyonu = '';\n"
    "if (caseType === 'non_product' || action === 'handoff') {\n"
    "  headerTitle = '⚠️ ŞİKAYET / İADE / TEMSİLCİ TALEBİ';\n"
    "  yetkiliAksiyonu = 'Müşteri memnuniyeti / İade prosedürü / Özel talep kontrolü';\n"
    "} else if (caseType === 'exact_code_compatibility' || intent === 'product_compatibility') {\n"
    "  headerTitle = '🛠️ UYUMLULUK VE PARÇA KONTROLÜ';\n"
    "  yetkiliAksiyonu = 'Şasi/Araç uyumluluk teyidi ve parça tespiti';\n"
    "} else if (caseType === 'cross_reference') {\n"
    "  headerTitle = '🔄 MUADİL / ÇAPRAZ REFERANS TALEBİ';\n"
    "  yetkiliAksiyonu = 'OEM/Muadil parça kodlarının çapraz eşleştirilmesi ve teyidi';\n"
    "} else if (caseType === 'exact_code_price_stock' || currentCodes.length > 0) {\n"
    "  headerTitle = '🔥 YÜKSEK NİYETLİ SATIŞ TALEBİ';\n"
    "  yetkiliAksiyonu = 'Stok ve net fiyat kontrolü';\n"
    "} else if (caseType === 'vehicle_based_search') {\n"
    "  headerTitle = '🚗 ARAÇ BAZLI PARÇA ARAMA';\n"
    "  yetkiliAksiyonu = 'Araç bilgilerine göre doğru parça tespiti ve fiyatlandırma';\n"
    "} else {\n"
    "  headerTitle = '📢 MÜŞTERİ TALEBİ / BİLDİRİM';\n"
    "  yetkiliAksiyonu = 'Talep inceleme ve dönüş yapma';\n"
    "}\n\n"
    "if (isUpdate) {\n"
    "  headerTitle = '🔄 SATIŞ TALEBİ GÜNCELLENDİ';\n"
    "}\n\n"
    "let talepOzeti = 'Stok ve net fiyat kontrolü';\n"
    "let yapilacaklar = '1. Stok kontrolü\\n2. KDV dâhil net fiyat\\n3. Bugün kargo durumu\\n4. Stok yoksa doğrulanmış alternatif';\n\n"
    "if (caseType === 'cross_reference') {\n"
    "  talepOzeti = 'Muadil / çapraz referans kontrolü';\n"
    "  yapilacaklar = '1. Kaynak kodu üretici kataloğunda doğrula\\n2. Talep edilen markalarda çapraz referans kontrol et\\n3. Doğrulanmış muadil kodunu belirle\\n4. Stok ve fiyat kontrolü yap';\n"
    "} else if (caseType === 'non_product') {\n"
    "  talepOzeti = 'Şikâyet / iade / temsilci talebi';\n"
    "  yapilacaklar = '1. Müşteri talebini veya şikâyetini incele\\n2. Müşteriyle en kısa sürede iletişime geç';\n"
    "} else if (caseType === 'exact_code_compatibility' || intent === 'product_compatibility') {\n"
    "  talepOzeti = 'Şasi/Araç uyumluluk teyidi';\n"
    "  yapilacaklar = '1. Araç marka/model/motor uyumluluğunu kontrol et\\n2. Parça referans numarasını doğrula\\n3. Güncel stok ve fiyat bilgisini ilet';\n"
    "} else if (caseType === 'vehicle_based_search') {\n"
    "  talepOzeti = 'Araç bilgisine göre parça arama';\n"
    "  yapilacaklar = '1. Araç bilgilerine (yıl/motor) uygun parça kodunu tespit et\\n2. Seçenekleri ve muadilleri kontrol et\\n3. Stok ve net fiyatları paylaş';\n"
    "}\n\n"
    "const formattedCodes = currentCodes.length > 0 ? currentCodes.map(c => `• ${c}`).join(' ') : 'Belirtilmedi';\n"
    "const codeStr = provenanceViolation ? `⚠️ ŞÜPHELİ AI KODU: ${unverifiedCode}\\n  Temizlenen Kodlar: ${formattedCodes}` : formattedCodes;\n"
    "const formattedVehicles = Array.isArray(entities.vehicles) && entities.vehicles.length > 0 ? entities.vehicles.map(v => typeof v === 'object' ? `• ${v.brand || ''} ${v.model || ''} ${v.year || ''}`.trim() : `• ${v}`).join(' ') : (caseType === 'exact_code_price_stock' ? 'Gerekli değil (Tam kod verildi)' : 'Belirtilmedi');\n\n"
    "const bildirim = `${headerTitle} — SLA 5 DK\\n` +\n"
    "  `Müşteri: ${senderName} (${senderNumber})\\n` +\n"
    "  `Ürün: ${codeStr}\\n` +\n"
    "  `Miktar: ${quantity}\\n` +\n"
    "  `Talep: ${talepOzeti}\\n` +\n"
    "  `Araç bilgisi: ${formattedVehicles}\\n` +\n"
    "  `Atanan: İsmail Özkaracan\\n\\n` +\n"
    "  `YAPILACAK:\\n${yapilacaklar}\\n\\n` +\n"
    "  (handoffReason ? `📌 Handoff Nedeni: ${handoffReason}\\n\\n` : '') +\n"
    "  `Müşteri mesajı:\\n\"${allMessagesText}\"\\n\\n` +\n"
    "  `🤖 AI Cevabı: ${replyDraft}`;\n\n"
    "if (!staticData._deliveryLedger) staticData._deliveryLedger = {};\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n"
    "if (action === 'handoff' || pauseAutomation === true) {\n"
    "  staticData._manualModes[senderNumber] = true;\n"
    "}\n"
    "// Her geçerli konuşma batch'i iki yöneticiye de özetlenir.\n"
    "shouldNotifyAdmin = true;\n"
    "// Muhatabin ismini soyismini soyleme kurali (Post-processor sanitization)\n"
    "if (senderName && typeof senderName === 'string' && senderName.trim().length > 1) {\n"
    "  const nameParts = senderName.trim().split(/\\s+/).filter(p => p.length > 1);\n"
    "  for (const part of nameParts) {\n"
    "    const nameRegex = new RegExp('\\\\b' + part.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + '\\\\b\\\\s*(?:[!,;:\\\\.]|(?:[bB]ey|[hH]an[iI]m|[aA]b[iI]|[eE]fend[iI]))?', 'gi');\n"
    "    replyDraft = replyDraft.replace(nameRegex, '').replace(/Merhaba\\s*,\\s*,/gi, 'Merhaba,').replace(/\\s+/g, ' ').trim();\n"
    "  }\n"
    "}\n"
    "// Ayrica genel Merhaba [Isim] sablonunda isim sizintisini temizle\n"
    "replyDraft = replyDraft.replace(/^Merhaba\\s+[A-Z?G?O?Ua-z?g?o?u]{2,15}\\s*(?:[bB]ey|[hH]an[iI]m)?\\s*([,!:\\\\.])/i, 'Merhaba$1');\n"
    "replyDraft = replyDraft.replace(/^Merhaba\\s+,/i, 'Merhaba,').replace(/^Merhaba\\s+([a-z?g?o?u])/i, 'Merhaba, $1').replace(/\\s+/g, ' ').trim();\n\n"
    "const shouldReplyCustomer = action !== 'ignore' && Boolean(replyDraft);\n"
    "const expectedChannels = { phoneA: true, phoneB: true };\n"
    "if (shouldReplyCustomer) expectedChannels['customer'] = true;\n"
    "if (Object.keys(expectedChannels).length > 0 && batchToken) {\n"
    "  staticData._deliveryLedger[batchToken] = {\n"
    "    createdAt: Date.now(),\n"
    "    expected: expectedChannels,\n"
    "    completed: {}\n"
    "  };\n"
    "  staticData._deliveryLedger = Object.assign({}, staticData._deliveryLedger);\n"
    "}\n\n"
    "return {\n"
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
    "    askVehicleInfo: Boolean(askVehicleInfo === true),\n"
    "    expectsReply: Boolean(parsed.expectsReply === true || askVehicleInfo === true),\n"
    "    validClaim: true\n"
    "  }\n"
    "};"
)

clear_batch_js = (
    "let currentInput = {};\n"
    "try {\n"
    "  currentInput = $input.item.json;\n"
    "} catch(e) {\n"
    "  console.error('[Finalize Batch] Girdi okunamadı:', e?.message || e);\n"
    "  return { json: { _skipped: true, reason: 'input_unreadable' } };\n"
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
            "body": "={{ JSON.stringify({ number: ($env.ADMIN_PHONE_A || '905052237182'), text: $json.bildirim }) }}",
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
            "body": "={{ JSON.stringify({ number: ($env.ADMIN_PHONE_B || '905306056066'), text: $json.bildirim }) }}",
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
            "body": "={{ JSON.stringify({ number: ($env.DEAD_LETTER_PHONE || '905052237182'), text: `🚨 SİSTEM HATASI (Dead-Letter)\n\n• Hedef/Müşteri: ${$json.senderNumber || $json.number || 'Bilinmiyor'}\n• Başarısız Kanal: ${$json.failedChannel || 'Bilinmeyen Kanal'}\n• Batch Token: ${$json.batchToken || 'Yok'}\n• Hata Detayı: ${JSON.stringify($json.error || $json.message || 'Evolution API HTTP Bağlantı/Timeout Hatası')}\n• Execution ID: ${$execution.id || 'Yok'}\n\nLütfen n8n panelinden ilgili execution kaydını kontrol edin.` }) }}",
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
            "_webhookSecret": os.environ.get('N8N_WEBHOOK_SECRET', 'F9a2Km7Qx8LpN3vB7jR5wY2tH6dK4mS')
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
