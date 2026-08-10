#!/usr/bin/env python3
"""Build the PostgreSQL-backed WhatsApp AI n8n workflow."""
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = Path(os.environ.get("N8N_WORKFLOW_OUTPUT", str(ROOT / "workflow.json")))
POSTGRES_ID = os.environ.get("N8N_POSTGRES_CREDENTIAL_ID", "hOSXsF6TYAQ3uQno")
POSTGRES_NAME = os.environ.get("N8N_POSTGRES_CREDENTIAL_NAME", "Postgres account")
EVOLUTION_ID = os.environ.get("N8N_EVOLUTION_CREDENTIAL_ID", "evolution-api")
EVOLUTION_NAME = os.environ.get("N8N_EVOLUTION_CREDENTIAL_NAME", "Evolution API")
OPENAI_ID = os.environ.get("N8N_OPENAI_CREDENTIAL_ID") or ""
OPENAI_NAME = os.environ.get("N8N_OPENAI_CREDENTIAL_NAME", "OpenAi account")


def node_id(name):
    stable_ids = {
        "Webhook1": "65f757d5-7045-45df-90aa-a959a4a10519",
        "Schedule Trigger": "0a90afa9-6731-5ce6-a4d0-76a4fc92898f",
        "OpenAI Chat Model1": "1b7c08e5-1da2-4a07-b017-370d41c50e85",
    }
    if name in stable_ids:
        return stable_ids[name]
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://filtreoto.online/n8n/{name}"))


def edge(name, index=0):
    return {"node": name, "type": "main", "index": index}


def code_node(name, code, position, mode="runOnceForEachItem"):
    return {
        "parameters": {"mode": mode, "jsCode": code},
        "id": node_id(name), "name": name, "type": "n8n-nodes-base.code",
        "typeVersion": 2, "position": position,
    }


def postgres_node(name, query, replacements, position):
    return {
        "parameters": {
            "operation": "executeQuery", "query": query,
            "options": {"queryReplacement": replacements},
        },
        "id": node_id(name), "name": name, "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6, "position": position,
        "credentials": {"postgres": {"id": POSTGRES_ID, "name": POSTGRES_NAME}},
    }


def if_node(name, expression, position):
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": [{
                    "id": node_id(name + " condition"), "leftValue": expression,
                    "rightValue": True, "operator": {"type": "boolean", "operation": "equals"},
                }],
                "combinator": "and",
            }, "options": {},
        },
        "id": node_id(name), "name": name, "type": "n8n-nodes-base.if",
        "typeVersion": 2.2, "position": position,
    }


def wait_node(name, amount, unit, position):
    return {
        "parameters": {"resume": "timeInterval", "amount": amount, "unit": unit},
        "id": node_id(name), "name": name, "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1, "position": position,
    }


normalize_js = r"""
const root = $json || {};
const payload = root.body?.body?.data || root.body?.data || null;
const headers = root.headers || {};
const headerSecret = String(headers['x-webhook-secret'] || headers['x-evolution-webhook-secret'] || '');
const queryToken = String(root.query?.token || '');
const webhookToken = headerSecret || queryToken;

// @lid normalizasyonu — gerçek telefon numarası için remoteJidAlt/senderPn fallback
const key = payload?.key || {};
const remoteJid = String(key.remoteJid || '');
const remoteJidAlt = String(key.remoteJidAlt || key.senderPn || '');
const isRemoteLid = remoteJid.toLowerCase().endsWith('@lid');
const effectiveJid = isRemoteLid
  ? (remoteJidAlt || remoteJid)
  : remoteJid;
// Preserve opaque WhatsApp LID addresses when Evolution did not provide
// remoteJidAlt/senderPn. Stripping @lid turns the LID into a false phone
// number and makes Evolution reject the later sendText request with 400.
const isLid = effectiveJid.toLowerCase().endsWith('@lid');
const senderNumber = isLid
  ? effectiveJid.replace(/[^0-9@a-zA-Z._-]/g, '')
  : effectiveJid
      .replace(/@s\.whatsapp\.net$|@g\.us$/gi, '')
      .replace(/[^0-9]/g, '');
const rawJid = remoteJid;

const fromMe = payload?.key?.fromMe === true;
const messageId = String(payload?.key?.id || '');
const isGroup = rawJid.endsWith('@g.us');
const isBroadcast = rawJid.endsWith('@broadcast');

// Protocol messages (calls, reactions, etc.) -> ignore
const msg = payload?.message || {};
const isProtocolMessage = Boolean(msg.protocolMessage || msg.reactionMessage);
const isEmpty = !msg.conversation && !msg.extendedTextMessage?.text
  && !msg.imageMessage && !msg.audioMessage && !msg.documentMessage && !msg.videoMessage;

// Media type detection
const isImage = Boolean(msg.imageMessage);
const isAudio = Boolean(msg.audioMessage);
const isDocument = Boolean(msg.documentMessage);
const isVideo = Boolean(msg.videoMessage);
const isMediaMessage = isImage || isAudio || isDocument || isVideo;
const mediaType = isImage ? 'image' : isAudio ? 'audio' : isDocument ? 'document' : isVideo ? 'video' : null;

// Extract caption if present, otherwise default text for media
const captionText = (isImage ? msg.imageMessage?.caption : null)
  || (isAudio ? msg.audioMessage?.caption : null)
  || (isDocument ? msg.documentMessage?.caption : null)
  || (isVideo ? msg.videoMessage?.caption : null) || '';
const text = String(msg.conversation || msg.extendedTextMessage?.text || captionText || '').trim();

// Media URL extraction
const mediaUrl = (isImage ? msg.imageMessage?.url : null)
  || (isAudio ? msg.audioMessage?.url : null)
  || (isDocument ? msg.documentMessage?.url : null)
  || (isVideo ? msg.videoMessage?.url : null) || null;
const mimetype = (isImage ? msg.imageMessage?.mimetype : null)
  || (isAudio ? msg.audioMessage?.mimetype : null)
  || (isDocument ? msg.documentMessage?.mimetype : null)
  || (isVideo ? msg.videoMessage?.mimetype : null) || null;

// For media without text, set specific fallback messages per type
const mediaFallback = {
  image: 'Görsel mesajınız alındı. Ürün detayını yazarak da paylaşabilirsiniz.',
  audio: 'Sesli mesajınızı şu anda işleyemiyoruz. Kısa bir metin olarak paylaşabilir misiniz?',
  document: 'Belge mesajınız alındı. İçeriğiyle ilgili kısa bir açıklama paylaşabilir misiniz?',
  video: 'Video mesajınız alındı. Ürün detayını yazarak da paylaşabilirsiniz.'
};
const displayText = text || (isMediaMessage ? (mediaFallback[mediaType] || '[Medya]') : '');

const commandRegex = /^\s*(\+\+|--|\?\?)\s*$/;
const commandMatch = text.match(commandRegex);
const isCommand = commandMatch !== null;
const authorizedCommand = fromMe && isCommand;
const command = authorizedCommand ? (commandMatch[1] === '++' ? 'pause' : commandMatch[1] === '--' ? 'resume' : 'check_mode') : null;
// Ignore: protocol messages, empty text without media, groups, broadcasts
const valid = Boolean(payload && messageId && senderNumber && !isGroup && !isBroadcast && !isProtocolMessage && !isEmpty && (!fromMe || command));
const correlationId = `${Date.now()}-${Math.random().toString(36).slice(2,10)}`;

// Rate limiting kontrolü (staticData üzerinden)
let rateLimitExceeded = false;
if (valid && !fromMe) {
  try {
    const getStaticData = typeof this?.getWorkflowStaticData === 'function'
      ? this.getWorkflowStaticData.bind(this)
      : null;
    if (getStaticData) {
      const staticData = getStaticData('global');
      if (!staticData._rateLimits) staticData._rateLimits = {};
      const rateLimitKey = `rate:${senderNumber}`;
      const lastMessage = staticData._rateLimits[rateLimitKey] || 0;
      const now = Date.now();
      const cooldownMs = 5000; // 5 saniye cooldown
      if (now - lastMessage < cooldownMs) {
        rateLimitExceeded = true;
      }
      staticData._rateLimits[rateLimitKey] = now;
      // Eski rate limit entries'leri temizle (5 dakika)
      const cutoff = now - 300000;
      for (const [key, timestamp] of Object.entries(staticData._rateLimits)) {
        if (timestamp < cutoff) delete staticData._rateLimits[key];
      }
    }
  } catch (_) {
    rateLimitExceeded = false;
  }
}

const message = {
  id: messageId, text: displayText || '[Medya]',
  type: mediaType || 'text',
  timestamp: Date.now(), mediaUrl, mimetype, isMediaMessage, mediaType
};
return { json: {
  valid, queryToken, webhookToken, authSource: headerSecret ? 'header' : 'query',
  senderNumber, senderName: String(payload?.pushName || senderNumber),
  messageId, fromMe, command, rawJid, message, correlationId,
  commandMessageId: messageId, commandRemoteJid: rawJid,
  commandParticipant: String(payload?.key?.participant || ''),
  isMediaMessage, mediaType, rateLimitExceeded
} };
""".strip()


validate_webhook_secret_js = r"""
const input = $json || {};
const webhookToken = String(input.webhookToken || input.queryToken || '');
const authSource = input.authSource || 'query';

// Token varlık kontrolü — eksikse reddet
if (!webhookToken || webhookToken === '' || webhookToken === 'undefined' || webhookToken === 'null') {
  return { json: Object.assign({}, input, {
    authorized: false,
    authSource: authSource,
    action: 'unauthorized',
    authFailureReason: 'missing_token',
    correlationId: input.correlationId || ''
  }) };
}

// Token mevcut — DB doğrulaması ingest_message fonksiyonunda yapılıyor
return { json: Object.assign({}, input, {
  authorized: true,
  authSource: authSource,
  action: null,
  authFailureReason: null,
  correlationId: input.correlationId || ''
}) };
""".strip()


apply_admin_number_filter_js = r"""
const source = $('Normalize Payload').item.json || {};
const settings = $json || {};
const configuredAdminNumbers = [settings.adminPhoneA, settings.adminPhoneB]
  .map(value => String(value || '').replace(/[^0-9]/g, ''))
  .filter(Boolean);
const authorizedCommand = source.fromMe === true
  && ['pause', 'resume', 'check_mode'].includes(source.command);
const senderNumber = String(source.senderNumber || '');
const isAdminNumber = !authorizedCommand && configuredAdminNumbers.includes(senderNumber);
return { json: {
  ...source,
  configuredAdminNumbers,
  isAdminNumber
} };
""".strip()


store_context_js = r"""
const row = $json || {};
const messages = Array.isArray(row.messages) ? row.messages : [];
const allMessagesText = String(row.all_messages_text || '');
// Prompt injection koruması — tehlikeli komutları temizle (İngilizce + Türkçe)
const sanitizePromptText = (value, limit = 1000) => String(value || '')
  // Unicode normalization (homoglyph bypass engelleme)
  .normalize('NFKC')
  // İngilizce injection kalıpları
  .replace(/ignore\s+previous\s+instructions/gi, '')
  .replace(/you\s+are\s+now/gi, '')
  .replace(/system\s*:/gi, '')
  .replace(/\[INST\]/gi, '')
  .replace(/\[\/INST\]/gi, '')
  .replace(/forget\s+everything/gi, '')
  .replace(/disregard\s+all/gi, '')
  .replace(/new\s+instructions/gi, '')
  .replace(/act\s+as/gi, '')
  .replace(/pretend\s+you\s+are/gi, '')
  .replace(/override\s+safety/gi, '')
  .replace(/\[SYSTEM\]/gi, '')
  .replace(/\[USER\]/gi, '')
  .replace(/do\s+anything\s+now/gi, '')
  .replace(/you\s+have\s+no\s+restrictions/gi, '')
  .replace(/jailbreak/gi, '')
  .replace(/dan\s+mode/gi, '')
  // Türkçe injection kalıpları
  .replace(/önceki\s+talimat(lar)?(ı)?\s+(yok\s+say|görmezden\s+gel|iptal\s+et|unut)/gi, '')
  .replace(/artık\s+sen/gi, '')
  .replace(/sistem\s*:/gi, '')
  .replace(/tüm\s+önceki\s+talimatları?\s+unut/gi, '')
  .replace(/yeni\s+talimatlar/gi, '')
  .replace(/farklı\s+bir\s+kişi\s+ol/gi, '')
  .replace(/rolün\s+değişti/gi, '')
  .replace(/şimdi\s+sensin/gi, '')
  .replace(/sen\s+artık/gi, '')
  .replace(/bana\s+yardım\s+et/gi, '')
  .replace(/talimatları\s+yoksay/gi, '')
  .replace(/güvenlik\s+protokollerini\s+devre\s+dışı\s+bırak/gi, '')
  .replace(/her\s+şeyi\s+yap/gi, '')
  .replace(/sınırsız\s+ol/gi, '')
  // Delimiter injection koruması
  .replace(/\]\s*\n\s*\[/g, '')
  .replace(/```system/gi, '')
  .replace(/```user/gi, '')
  .replace(/<\|im_start\|>/gi, '')
  .replace(/<\/im_start>/gi, '')
  .slice(0, limit);
const sanitizedText = sanitizePromptText(allMessagesText);
let chatMemoryRows = row.chat_memory;
if (typeof chatMemoryRows === 'string') {
  try { chatMemoryRows = JSON.parse(chatMemoryRows); } catch (_) { chatMemoryRows = []; }
}
const chatMemoryText = (Array.isArray(chatMemoryRows) ? chatMemoryRows : [])
  .slice(-20)
  .map(item => {
    const role = item?.role === 'assistant' ? 'Asistan' : 'Müşteri';
    const content = sanitizePromptText(item?.content || '', 600);
    return content ? `${role}: ${content}` : '';
  })
  .filter(Boolean)
  .join('\\n');
const _codePatterns = [
  /\b[A-Z]{1,4}\s?\d{2,6}(?:\/\d{1,4})?[A-Z]{0,3}\b/gi,
  /\b[A-Z0-9]{2,10}[.\/-][A-Z0-9]{1,10}\b/g,
  /\b[A-Z]{1,4}\s\d{2,6}(?:\s\d{1,6})?\b/g,
  /\b[A-Z]\d{2,6}[A-Z]{0,3}\b/g,
];
const detectedCodes = [...new Set(_codePatterns.flatMap(p => allMessagesText.match(p) || [])
  .map(x => x.trim()).filter(x => /\d/.test(x)))].slice(0, 20);
const correlationId = String(row.correlationId || '');
return { json: {
  ...row,
  senderNumber: String(row.sender_number || row.senderNumber || ''),
  senderName: String(row.sender_name || row.senderName || row.sender_number || ''),
  batchToken: String(row.batch_token || row.batchToken || ''),
  messageCount: Number(row.message_count || messages.length),
  allMessagesText, detectedCodes, aiAttemptCount: Number(row.ai_attempt_count || 0),
  assigneeName: String(row.assignee_name || 'İsmail Özkaracan'),
  correlationId: String(row.correlation_id || row.correlationId || ''),
  isMediaMessage: Boolean(row.is_media_message || row.isMediaMessage),
  mediaType: String(row.media_type || row.mediaType || ''),
  chatMemoryText,
  _prompt: `${chatMemoryText ? `Önceki sohbet belleği:\n${chatMemoryText}\n\n` : ''}Müşteri mesajları:\n${sanitizedText}\n\n[Yalnız tanımlı JSON şemasında cevap ver. correlationId: ${correlationId}]`
} };
""".strip()


system_prompt = """Sen otomotiv filtre satışı için güvenli bilgi çıkarımı yapan bir asistansın.
Yalnız JSON üret. Şema:
{"intent":"price_stock|compatibility|cross_reference|return_complaint|complaint|human_request|greeting|unclear|other","caseType":"exact_code_price_stock|exact_code_compatibility|cross_reference|partial_code|non_product|greeting|unclear|other","entities":{"productCodes":[],"preferredBrands":[],"quantity":"Belirtilmedi","vehicles":[{"brand":null,"model":null,"year":null,"engine":null,"power":null,"vin":null,"raw":null}]},"replyDraft":"","confidence":0.0,"expectsReply":false}
Fiyat, stok, kargo veya uyumluluk doğrulanmış gibi gösterme. Müşterinin yazmadığı ürün kodunu üretme. Eksik araç bilgisinde motor hacmi ve beygir veya şasi iste. non_product caseType'ında intent ayrımı:
- return_complaint: müşteri iade veya değişim istiyor
- complaint: müşteri memnuniyetsizliği, sorun bildiriyor
- human_request: müşteri insan temsilci istiyor
- other: diğer destek talepleri

KRİTİK BİLGİ TEKRARI KURALI:
- Bu sohbette veya önceki sohbet belleğinde VIN/şasi verildiyse bir daha ASLA isteme.
- 17 haneli alfanümerik dizi VIN/şasi numarasıdır; otomatik kabul et.
- Marka + model + yıl + motor bilgisi VIN olmadan da yeterlidir.
- Önceki bilgileri kısa özetle ve doğrudan sonraki işleme geç.

FİRMA BİLGİLERİ (yalnızca ilgili soru sorulursa kullan):
- Denizli'den Aras Kargo ile gönderim yapılır; standart teslimat 2-3 iş günüdür ve 1-3 gün arası değişebilir.
- Cumartesi teslimat garantisi verilmez.
- N11, Trendyol ve Amazon gibi pazaryerlerinde satış yoktur; sipariş filtreoto.com üzerinden verilir.
- 3D Secure ödeme vardır; Etbis'e kayıtlıyız ve talep edilirse distribütör faturası paylaşılabilir.
- İade koşullarını kesinleştirmeden söz verme; gerektiğinde temsilciye aktar.
- Stok, fiyat, uyumluluk ve kargo sonucunu veriyle doğrulanmadıysa kesinleştirme.
- "Uzmanımız bakacak" gibi gereksiz devir cümleleri kurma; mevcut bilgilerle ilerle.

Confidence rehberliği:
- 0.9+: Tam kod bulundu, net talep
- 0.7-0.9: Kısmi bilgi, araç bilgisi var
- 0.5-0.7: Belirsiz, ek bilgi gerekli
- <0.5: Çok belirsiz, insan devri

Kritik sınıflandırma kuralı:
- Selamlama tek başına varsa `greeting` kullan.
- Selamlama ile birlikte satın alma, teklif, toplu alım, miktar veya B2B sinyali varsa `greeting` yerine talebi sınıflandır.

Örnekler:
Input: "BOSCH F026400287 var mı fiyat ne kadar"
Output: {"intent":"price_stock","caseType":"exact_code_price_stock","entities":{"productCodes":[{"code":"BOSCH F026400287"}],"preferredBrands":["BOSCH"],"quantity":"Belirtilmedi","vehicles":[]},"replyDraft":"","confidence":0.95,"expectsReply":false}

Input: "Fiat Egea 2019 yağ filtresi lazım"
Output: {"intent":"compatibility","caseType":"exact_code_compatibility","entities":{"productCodes":[],"preferredBrands":[],"quantity":"Belirtilmedi","vehicles":[{"brand":"Fiat","model":"Egea","year":"2019","engine":null,"power":null,"vin":null,"raw":"Fiat Egea 2019"}]},"replyDraft":"","confidence":0.70,"expectsReply":true}

Input: "Siparişim hala gelmedi 3 gün oldu şikayetçiyim"
Output: {"intent":"complaint","caseType":"non_product","entities":{"productCodes":[],"preferredBrands":[],"quantity":"Belirtilmedi","vehicles":[]},"replyDraft":"","confidence":0.90,"expectsReply":false}

Input: "Merhaba"
Output: {"intent":"greeting","caseType":"greeting","entities":{"productCodes":[],"preferredBrands":[],"quantity":"Belirtilmedi","vehicles":[]},"replyDraft":"","confidence":0.95,"expectsReply":false}

Input: "MN134 ve HU7012 filtre var mı"
Output: {"intent":"price_stock","caseType":"exact_code_price_stock","entities":{"productCodes":[{"code":"MN134"},{"code":"HU7012"}],"preferredBrands":[],"quantity":"Belirtilmedi","vehicles":[]},"replyDraft":"","confidence":0.92,"expectsReply":false}

Input: "Merhabalar. 16 Kalem Filtre alımı için fiyat almak istiyoruz"
Output: {"intent":"price_stock","caseType":"partial_code","entities":{"productCodes":[],"preferredBrands":[],"quantity":16,"vehicles":[]},"replyDraft":"","confidence":0.80,"expectsReply":true}"""


parse_ai_js = r"""
const current = $json || {};
const ctx = $('Store Context').item.json;

// Media message auto-handoff: skip AI, handoff to admin
const isMediaMessage = ctx.isMediaMessage === true;
const hasText = Boolean(String(ctx.allMessagesText || '').replace(/^\s*\[Medya\]\s*$/, '').trim());
if (isMediaMessage && !hasText) {
  const mediaLabels = { image: 'Görsel', audio: 'Ses', document: 'Belge', video: 'Video' };
  const mediaLabel = mediaLabels[ctx.mediaType] || 'Medya';
  return { json: {
    ...ctx, intent: 'other', caseType: 'non_product', entities: {},
    cevap: `${mediaLabel} mesajınızı aldık, ürün uzmanımız inceliyor. İçeriği tek cümleyle özetler misiniz? Örneğin "bu filtrenin muadili" demeniz dönüşümüzü çok hızlandırır.`,
    bildirim: `📩 ${mediaLabel} MESAJI\n👤 ${ctx.senderName} · ${ctx.senderNumber}\n\n💬 Müşteri "${ctx.allMessagesText || '[Medya]'}"\n\n📩 Uzmanına Aktarıldı\n"Mesajınız alındı. İncelemek üzere uzman ekibimize aktarıyorum."`,
    notifyAdmins: true, replyCustomer: true, pauseAutomation: true,
    askVehicleInfo: false, expectsReply: false, action: 'handoff',
    handoffReason: `${mediaLabel} mesajı - manuel değerlendirme gerekli`,
    retryAi: false, replyStatus: 'handed_off', deliveryStatus: 'pending',
    parseFailureCode: null, parseFailureMessage: null,
    fingerprint: `media:${ctx.mediaType}:${ctx.senderNumber}`
  } };
}

const raw = current.output ?? current.aiResult ?? current;
let parsed;
try {
  parsed = typeof raw === 'object'
    ? raw
    : JSON.parse(String(raw).replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim());
} catch (error) {
  parsed = { intent: 'unclear', caseType: 'unclear', entities: {}, confidence: 0, _parseError: true };
}

const allowed = new Set(['exact_code_price_stock','exact_code_compatibility','cross_reference','partial_code','non_product','greeting','unclear','other']);
const originalText = String(ctx.allMessagesText || '');
const plainText = originalText.replace(/^\s*\d+\.\s*(?:\[[^\]]+\]\s*)?/, '').trim();
const historyText = String(ctx.chatMemoryText || '');
const vehicleSourceText = `${plainText}\n${historyText}`;
const textUpper = plainText.toUpperCase();
let intent = String(parsed.intent || 'other');
let caseType = String(parsed.caseType || 'other');
let entities = parsed.entities && typeof parsed.entities === 'object' ? parsed.entities : {};
let confidence = typeof parsed.confidence === 'number' ? parsed.confidence : Number(parsed.confidence?.caseType || 0);
let reply = String(parsed.replyDraft || '').trim();
const SLA_TEXT = 'mesai saatleri içinde';
const BRAND_LINE = 'Filtre Oto';
const _tz = 'Europe/Istanbul';
const _hour = Number(new Intl.DateTimeFormat('tr-TR', { hour: 'numeric', hour12: false, timeZone: _tz }).format(new Date()));
const _day = new Date().toLocaleDateString('en-US', { weekday: 'short', timeZone: _tz });
const _dateKey = new Intl.DateTimeFormat('en-CA', { timeZone: _tz }).format(new Date());
const HOLIDAYS = ['2026-01-01','2026-03-20','2026-03-21','2026-03-22','2026-04-23','2026-05-01','2026-05-19','2026-05-27','2026-05-28','2026-05-29','2026-07-15','2026-08-30','2026-10-28','2026-10-29'];
const BUSINESS_HOURS = { Mon: [9, 18], Tue: [9, 18], Wed: [9, 18], Thu: [9, 18], Fri: [9, 18], Sat: [9, 18], Sun: null };
const _window = HOLIDAYS.includes(_dateKey) ? null : BUSINESS_HOURS[_day];
const isBusinessHours = Array.isArray(_window) && _hour >= _window[0] && _hour < _window[1];
const SLA_LINE = isBusinessHours
  ? `Mesai ${SLA_TEXT} dönüş yapacağız.`
  : 'Mesai dışındayız; talebiniz sıraya alındı, ilk iş saatinde dönüş yapılacak.';

// --- Type validation & length limits ---
if (typeof confidence !== 'number' || isNaN(confidence)) confidence = 0;
confidence = Math.max(0, Math.min(1, confidence));
if (!Array.isArray(entities.productCodes)) entities.productCodes = [];
entities.productCodes = entities.productCodes.slice(0, 20).map(c => {
  if (typeof c === 'string') return { code: c };
  if (c && typeof c === 'object' && typeof c.code === 'string') return { code: c.code };
  return null;
}).filter(Boolean);
if (!Array.isArray(entities.vehicles)) entities.vehicles = [];
entities.vehicles = entities.vehicles.slice(0, 5).map(v => {
  if (!v || typeof v !== 'object') return null;
  return {
    brand: typeof v.brand === 'string' ? v.brand : null,
    model: typeof v.model === 'string' ? v.model : null,
    year: typeof v.year === 'string' || typeof v.year === 'number' ? v.year : null,
    engine: typeof v.engine === 'string' ? v.engine : null,
    power: typeof v.power === 'string' || typeof v.power === 'number' ? v.power : null,
    vin: typeof v.vin === 'string' ? v.vin : null,
    raw: typeof v.raw === 'string' ? v.raw : null,
  };
}).filter(Boolean);
if (!Array.isArray(entities.preferredBrands)) entities.preferredBrands = [];
entities.preferredBrands = entities.preferredBrands.filter(b => typeof b === 'string').slice(0, 10);
if (typeof entities.quantity !== 'string' && typeof entities.quantity !== 'number') entities.quantity = 'Belirtilmedi';
// Deterministik adet yakalama — LLM kaçırırsa metinden çıkar
if (entities.quantity === 'Belirtilmedi') {
  const qMatch = plainText.match(/(\d{1,4})\s*(?:adet|tane|kalem|ad\.|ad\b|x)\b/i)
    || plainText.match(/\b(?:adet|tane)\s*[:=]?\s*(\d{1,4})\b/i);
  if (qMatch) {
    const q = parseInt(qMatch[1], 10);
    if (q > 0 && q <= 9999) entities.quantity = q;
  }
}
const isBulkOrder = typeof entities.quantity === 'number' && entities.quantity >= 10;
if (reply.length > 700) reply = reply.slice(0, 700);
if (!['price_stock','compatibility','cross_reference','return_complaint','complaint','human_request','greeting','unclear','other'].includes(intent)) intent = 'other';
// --- End validation ---

let pauseAutomation = false;
let notifyAdmins = true;
let action = 'reply';
let handoffReason = '';
let askVehicleInfo = false;
let retryAi = false;
let fallbackType = null;

const filterRequest = /\b(yağ|yag|hava|yakıt|yakit|polen|kabin|şanzıman|sanziman)\s+filtresi?\b|\bfiltre\b/i.test(plainText);
const yearMatch = vehicleSourceText.match(/\b(19\d{2}|20\d{2})\b/);
const brands = ['Fiat','Renault','Ford','Volkswagen','VW','Opel','Peugeot','Citroen','Toyota','Honda','Hyundai','Kia','Mercedes','BMW','Audi','Skoda','Seat','Dacia','Nissan'];
const brand = brands.find(item => new RegExp(`\\b${item}\\b`, 'i').test(vehicleSourceText));
let extractedVehicle = '';
if (brand) {
  const afterBrand = vehicleSourceText.slice(vehicleSourceText.toLocaleLowerCase('tr-TR').indexOf(brand.toLocaleLowerCase('tr-TR')) + brand.length);
  const modelPart = afterBrand.split(/\b(?:19\d{2}|20\d{2})\b/)[0]
    .replace(/\b(?:yağ|yag|hava|yakıt|yakit|polen|kabin|filtre|filtresi|arıyorum|ariyorum|için|icin)\b/gi, ' ')
    .replace(/[^\p{L}\p{N}.-]+/gu, ' ').trim().split(/\s+/).slice(0, 3).join(' ');
  extractedVehicle = [brand === 'VW' ? 'Volkswagen' : brand, modelPart, yearMatch?.[1] || ''].filter(Boolean).join(' ').trim();
}

const vehicleRequestDetected = filterRequest && Boolean(brand || yearMatch);
const deterministicCase = vehicleRequestDetected || (Array.isArray(ctx.detectedCodes) && ctx.detectedCodes.length > 0)
  || ['exact_code_price_stock','exact_code_compatibility','cross_reference','partial_code','greeting','non_product'].includes(caseType);

// Normalize caseType aliases
const caseTypeAliases = { 'exact_code_stock': 'exact_code_price_stock' };
if (caseTypeAliases[caseType]) caseType = caseTypeAliases[caseType];

if (!allowed.has(caseType)) {
  caseType = 'unclear'; action = 'handoff'; pauseAutomation = true; notifyAdmins = true;
  handoffReason = 'AI şema doğrulaması başarısız';
}

if (!Array.isArray(entities.vehicles)) entities.vehicles = [];
if (extractedVehicle && !entities.vehicles.some(v => String(v?.raw || v || '').toLocaleLowerCase('tr-TR').includes(extractedVehicle.toLocaleLowerCase('tr-TR')))) {
  entities.vehicles.unshift({ raw: extractedVehicle, brand: brand === 'VW' ? 'Volkswagen' : brand, model: extractedVehicle.replace(new RegExp(`^${brand === 'VW' ? 'Volkswagen' : brand}\\s*`, 'i'), '').replace(/\s+(?:19\d{2}|20\d{2})$/, ''), year: yearMatch?.[1] || null });
}
const vehicleStrings = entities.vehicles.map(v => {
  if (typeof v === 'string') return v.trim();
  return String(v?.raw || [v?.brand, v?.model, v?.year, v?.engine].filter(Boolean).join(' ')).trim();
}).filter(Boolean);
const vehicleBlob = `${vehicleSourceText} ${vehicleStrings.join(' ')}`;
const hasVin = /\b[A-HJ-NPR-Z0-9]{17}\b/i.test(vehicleBlob);
const hasEngine = /\b\d[.,]\d\s*(?:TDI|TSI|DCI|HDI|MPI|CDTI|CRDI|BENZİN|DİZEL)?\b/i.test(vehicleBlob);
const hasPower = /\b\d{2,3}\s*(?:kw|hp|bg|beygir)\b/i.test(vehicleBlob);
const hasModel = Boolean(brand && extractedVehicle.replace(new RegExp(`^${brand === 'VW' ? 'Volkswagen' : brand}\\s*`, 'i'), '').replace(/\s+(?:19\d{2}|20\d{2})$/, '').trim());
const missingVehicleFields = [];
if (!brand) missingVehicleFields.push('marka');
if (!hasModel) missingVehicleFields.push('model');
if (!yearMatch) missingVehicleFields.push('üretim yılı');
if (!hasVin && !hasEngine) missingVehicleFields.push('motor hacmi (CC)');
if (!hasVin && !hasPower) missingVehicleFields.push('motor gücü (kW/HP)');
const vehicleComplete = hasVin || missingVehicleFields.length === 0;

let codes = Array.isArray(entities.productCodes) ? entities.productCodes : [];
if (codes.length === 0 && Array.isArray(ctx.detectedCodes)) codes = ctx.detectedCodes.map(code => ({ code }));
const codePatterns = [
  /^[A-Z]{1,4}\s?\d{2,6}(?:\/\d{1,4})?[A-Z]{0,3}$/i,
  /^[A-Z0-9]{2,10}[.\/-][A-Z0-9]{1,10}$/i,
  /^[A-Z]{1,4}\s\d{2,6}(?:\s\d{1,6})?$/i,
  /^[A-Z]\d{2,6}[A-Z]{0,3}$/i,
];
const plausibleCode = (code) => codePatterns.some(p => p.test(code));
const normalizedCodes = codes.map(c => String(c?.code || c?.raw || c || '').trim())
  .filter(code => plausibleCode(code));
entities.productCodes = normalizedCodes.map(code => ({ code }));
if (normalizedCodes.length > 0 && ['other','unclear','partial_code'].includes(caseType)) {
  caseType = 'exact_code_price_stock';
  intent = 'price_stock';
  action = 'reply';
  pauseAutomation = false;
  handoffReason = '';
} else if (caseType === 'exact_code_price_stock' && normalizedCodes.length === 0) {
  // Never promise a code-based stock/price lookup when no code was extracted.
  caseType = 'partial_code';
  intent = 'other';
  reply = '';
}
const invented = normalizedCodes.filter(code => !textUpper.includes(code.toUpperCase()));
if (invented.length > 0) {
  const hadProductCodes = entities.productCodes.length > 0;
  entities.productCodes = [];
  normalizedCodes.length = 0;
  caseType = 'unclear';
  action = 'handoff'; pauseAutomation = true; notifyAdmins = true;
  handoffReason = 'Mesajda bulunmayan ürün kodu engellendi';
  reply = hadProductCodes
    ? `Paylaştığınız kodu birebir doğrulamak için ürün uzmanımıza ilettik. Kutu veya ürün üzerindeki yazının fotoğrafını gönderebilir misiniz? Eşleştirmeyi çok daha hızlı tamamlarız. ${SLA_LINE}`
    : `Aracınıza uygun ürünü doğru seçebilmek için talebinizi ürün uzmanımıza ilettik. Ruhsattaki şasi numarasını paylaşır mısınız? Eşleştirme böylece kesinleşir. ${SLA_LINE}`;
}

// --- partial_code sub-classification ---
let partialSubType = '';
if (caseType === 'partial_code') {
  if (normalizedCodes.length > 0) {
    partialSubType = 'incomplete_code';
  } else if (brand || yearMatch) {
    partialSubType = 'vehicle_info_only';
  } else {
    partialSubType = 'missing_all';
  }
}

const purchaseIntent = /\b(al[ıi]m|alacağ[ıi]z|almak istiy|sipariş\s*(?:ver|geç|oluştur)|teklif|proforma|fiyat\s*(?:al|listesi|ver|çalışma))/i.test(plainText);
const quantitySignal = isBulkOrder || /\b\d{1,4}\s*(?:kalem|adet|tane|kutu|koli|palet|çeşit)\b/i.test(plainText);
const b2bSignal = /\b(toptan|bayi|bayilik|filo|oto\s*sanayi|kurumsal|ihale)\b/i.test(plainText);
const productContext = filterRequest || vehicleRequestDetected || normalizedCodes.length > 0;
const commercialLead = (purchaseIntent || quantitySignal || b2bSignal) && productContext;

if (parsed._parseError) {
  if (deterministicCase) {
    reply = '';
  } else {
    action = 'retry'; retryAi = true;
  }
} else if (confidence < 0.55 && !deterministicCase && !['greeting','unclear'].includes(intent)) {
  action = 'handoff'; pauseAutomation = true; notifyAdmins = true;
  handoffReason ||= 'Düşük AI güven skoru';
}

if (caseType === 'exact_code_compatibility') {
  notifyAdmins = true;
  if (!vehicleComplete && action !== 'handoff') {
    askVehicleInfo = true;
    reply = `Aracınıza uyan filtreyi net seçebilmemiz için tek bir bilgi yeterli: **ruhsattaki şasi (VIN) numarası**. Şasi ile motor tipini birebir eşleştirip yanlış parça riskini sıfırlıyoruz. Şasiyi paylaşabilir misiniz? Alternatif olarak marka, model, yıl ve motor hacmini de yazabilirsiniz.`;
  } else if (action !== 'handoff') {
    reply = `Araç bilgilerinizi aldım; ${extractedVehicle || 'aracınız'} için uyumlu filtre setini kontrol ediyorum. Sadece bu filtreyi mi istersiniz, yoksa periyodik bakım setinin tamamını mı görelim? ${SLA_LINE}`;
  }
} else if (caseType === 'exact_code_price_stock' && action !== 'handoff') {
  notifyAdmins = true;
  if (normalizedCodes.length === 1) {
    reply = `Kodu aldık; güncel stok ve fiyatı kontrol ediyoruz. Doğru ürünü ilk seferde gönderebilmemiz için kaç adet düşündüğünüzü yazar mısınız? ${SLA_LINE}`;
  } else {
    let codeList;
    if (normalizedCodes.length <= 3) {
      codeList = normalizedCodes.join(', ');
    } else if (normalizedCodes.length <= 10) {
      codeList = normalizedCodes.slice(0, 3).join(', ') + ` ve ${normalizedCodes.length - 3} ürün daha`;
    } else {
      codeList = `${normalizedCodes.length} ürün kodu`;
    }
    reply = `${codeList} için güncel stok ve fiyat kontrolünü başlattık. Listeyi tek seferde toparlayabilmemiz için her bir üründen kaçar adet gerektiğini yazar mısınız? ${SLA_LINE}`;
  }
} else if (caseType === 'cross_reference') {
  notifyAdmins = true;
  reply = `Muadil aramasını başlattık. Çapraz referans tablomuzda aynı teknik ölçülere sahip alternatifleri çıkarıyoruz. Bir marka tercihiniz var mı, yoksa fiyat/performans açısından en uygununu mu önerelim? ${SLA_LINE}`;
} else if (caseType === 'partial_code') {
  if (partialSubType === 'incomplete_code') {
    reply = 'Kodun bir kısmını görüyoruz ama tam eşleşme için tamamı gerekli. En kolayı şu: eski filtrenin üzerindeki yazının fotoğrafını gönderebilir misiniz? Kodu biz okuyalım. Dilerseniz kodu yazarak da iletebilirsiniz.';
  } else if (partialSubType === 'vehicle_info_only') {
    reply = 'Aracınızı not aldık. Aynı modelde farklı motor seçenekleri farklı filtre kullanıyor; yanlış parça göndermemek için ruhsattaki şasi numarasını paylaşır mısınız? Motor hacmi ve yakıt türünü yazmanız da yeterli olur.';
  } else if (partialSubType === 'bulk_request') {
    reply = 'Merhaba, hoş geldiniz. Talebiniz için hemen fiyat çalışması yapalım. Ürün kodlarını yazabilir ya da mevcut listenizin fotoğrafını gönderebilirsiniz. Kodlar elinizde değilse araçların şasi numaraları da yeterli.';
  } else {
    reply = 'Size en hızlı şekilde yardımcı olabilmemiz için iki yoldan biri yeterli: ürünün kodu ya da ruhsattaki şasi numarası. Hangisi elinizin altındaysa onu yazar mısınız? Gerisini biz halledelim.';
  }
} else if (caseType === 'greeting') {
  if (commercialLead) {
    caseType = 'partial_code';
    partialSubType = 'bulk_request';
    intent = 'price_stock';
    reply = 'Merhaba, hoş geldiniz. Talebiniz için hemen fiyat çalışması yapalım. Ürün kodlarını yazabilir ya da mevcut listenizin fotoğrafını gönderebilirsiniz. Kodlar elinizde değilse araçların şasi numaraları da yeterli.';
  } else {
    reply = `Merhaba, ${BRAND_LINE}'ya hoş geldiniz. Filtre kodunu ya da aracınızın şasi numarasını yazmanız yeterli — uygun ürünü birlikte netleştirelim. Hangi araç için bakıyorsunuz?`;
  }
} else if (caseType === 'non_product' || intent === 'return_complaint') {
  action = 'handoff'; pauseAutomation = true; notifyAdmins = true;
  if (intent === 'return_complaint') {
    handoffReason ||= 'İade/değişim talebi';
    const hasOrderNum = /sipari[şs]|order|s[ıi]ra.*no|fatura/i.test(plainText);
    const hasDescription = plainText.length > 30;
    if (hasOrderNum && hasDescription) {
      reply = `Talebinizi aldık, sipariş kaydınızı inceleme sırasına aldık. İade ve değişim süreçlerini müşteri temsilcimiz baştan sona takip eder. ${SLA_LINE}`;
    } else if (hasOrderNum) {
      reply = 'Sipariş bilginizi aldık. Süreci doğru başlatabilmemiz için ürünle ilgili sorunu tek cümleyle anlatır mısınız? Örneğin "araçla uyumsuz" veya "hasarlı geldi" demeniz yeterli.';
    } else {
      reply = 'Talebinizi aldık. Kaydınızı hızlıca bulabilmemiz için sipariş numaranızı yazar mısınız? Numarayı bulamıyorsanız sipariş tarihi ve ürün adı da yeterli olur.';
    }
  } else if (intent === 'complaint') {
    handoffReason ||= 'Müşteri şikayeti';
    reply = `Yaşadığınız olumsuzluk için özür dileriz. Konuyu öncelikli inceleme sırasına aldık ve sorumlu bir temsilci atadık. ${SLA_LINE}`;
  } else if (intent === 'human_request') {
    handoffReason ||= 'Temsilci talebi';
    reply = `Sizi müşteri temsilcimize bağlıyorum. ${SLA_LINE} Bu arada aracınızı veya aradığınız ürünü yazarsanız, temsilcimiz konuya hazırlanmış olarak döner.`;
  } else {
    handoffReason ||= 'Destek talebi';
    reply = `Talebinizi aldık ve ilgili ekibe yönlendirdik. ${SLA_LINE} Konuyla ilgili eklemek istediğiniz bir detay varsa şimdi yazabilirsiniz.`;
  }
}

const operationalQuestion = !['complaint', 'return_complaint', 'human_request'].includes(intent);
const asksMarketplace = /\b(n11|trendyol|amazon|pazaryeri|pazar yeri)\b/i.test(plainText);
const asksShipping = /\b(kargo|teslim|cumartesi|yarın|yarin|ne zaman gelir)\b/i.test(plainText);
const asksAuthenticity = /\b(orijinal|fatura|etbis|3d\s*secure|güvenli ödeme|guvenli odeme)\b/i.test(plainText);
if (operationalQuestion && asksMarketplace) {
  reply = 'N11, Trendyol ve Amazon gibi pazaryerlerinde satışımız yoktur. Siparişinizi filtreoto.com üzerinden verebilirsiniz.';
  action = 'reply'; pauseAutomation = false; notifyAdmins = false; handoffReason = '';
} else if (operationalQuestion && asksShipping) {
  reply = 'Denizli\'den Aras Kargo ile gönderiyoruz. Standart teslimat 2-3 iş günüdür; süre 1-3 gün arasında değişebilir. Cumartesi teslimat garantisi veremiyoruz.';
  action = 'reply'; pauseAutomation = false; notifyAdmins = false; handoffReason = '';
} else if (operationalQuestion && asksAuthenticity) {
  reply = 'Ürünlerimiz orijinaldir. Talep ederseniz distribütör faturası paylaşabiliriz; firmamız Etbis\'e kayıtlıdır ve 3D Secure ile güvenli ödeme vardır.';
  action = 'reply'; pauseAutomation = false; notifyAdmins = false; handoffReason = '';
}

const safetyText = String(reply || '')
  .normalize('NFKD')
  .replace(/[\u0300-\u036f]/g, '')
  .replace(/\u0131/g, 'i')
  .replace(/\u0130/g, 'i')
  .replace(/\u0049/g, 'i')
  .toLowerCase();
// Daha spesifik regex — false positive riskini azalt
const unsafeClaim = /\b\d+(?:[.,]\d+)?\s*(?:tl|₺)\b/i.test(safetyText) ||
  /\bstok(?:ta|larimizda|umuzda)\s+(?:var|mevcut)\b/i.test(safetyText) ||
  /\bkesin(?:likle)?\s+(?:uyar|uyumludur|calisir)\b/i.test(safetyText) ||
  /\bbugun\s+kargo\b/i.test(safetyText) ||
  /\bayni\s+gun\s+kargo\b/i.test(safetyText) ||
  /\bhemen\s+kargoya\s+veriyoruz\b/i.test(safetyText) ||
  /\bgarantili\b/i.test(safetyText) ||
  /\borijinal\s+parca\b/i.test(safetyText) ||
  /\bbirebir\s+karsiligi\b/i.test(safetyText) ||
  /\btam\s+karsiligi\b/i.test(safetyText) ||
  /\bdirekt\s+takilir\b/i.test(safetyText) ||
  /\brahatlikla\s+kullanabilirsiniz\b/i.test(safetyText) ||
  /\bsorunsuz\s+kullanabilirsiniz\b/i.test(safetyText) ||
  /\bmevcut\s+gorunuyor\b/i.test(safetyText) ||
  /\bstokta\s+\d+\s+adet\b/i.test(safetyText) ||
  /\bfiyat[ıi]?\s*[:=]?\s*\d+/i.test(safetyText);
if (unsafeClaim) {
  reply = `Talebinizi ürün uzmanımıza ilettik; güncel bilgiyi doğrulayıp size net olarak döneceğiz. ${SLA_LINE}`;
  notifyAdmins = true;
}
// Unclear intent fallback (when AI can't understand the message)
if (!reply && action !== 'handoff') {
  reply = 'Talebinizi tam çözemedim, doğru yönlendirebilmem için kısa bir bilgi yeterli: filtre kodu mu arıyorsunuz, yoksa aracınıza uygun ürün mü? Hangisiyse yazın, hemen ilgilenelim.';
  handoffReason = 'unclear_intent';
  action = 'reply';
}

// Generic last-resort fallback
if (!reply) reply = `Talebinizi aldık ve ekibimize ilettik. ${SLA_LINE}`;
const emojiForCase = {
  exact_code_price_stock: '📦',
  exact_code_compatibility: '🛠️',
  cross_reference: '🔄',
  partial_code: '🔎',
  greeting: '👋',
  non_product: '🤝',
  unclear: '📝',
  other: '📌'
};
const emojiRegex = /^[\u{1F300}-\u{1FAFF}\u2600-\u27BF\u{2702}-\u{27B0}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}✅✔️❌⚠️🛑⏸️🔔📊]/u;
const noEmojiIntents = ['complaint', 'return_complaint'];
const suppressEmoji = noEmojiIntents.includes(intent);
const replyEmoji = emojiForCase[caseType] || '📌';
if (!suppressEmoji && !emojiRegex.test(reply)) reply = `${replyEmoji} ${reply}`;
// Only add checkmark if not already present
if (!suppressEmoji && !reply.includes('✅') && ['exact_code_price_stock','exact_code_compatibility','cross_reference'].includes(caseType)) reply = `${reply} ✅`;
let replyStatus = 'generated';
if (action === 'ignore') replyStatus = 'suppressed';
else if (retryAi) replyStatus = 'pending_retry';
else if (action === 'handoff') replyStatus = 'handed_off';
else if (pauseAutomation) replyStatus = 'suppressed_manual';
else replyStatus = 'generated';

let deliveryStatus = 'pending';
// deliveryStatus will be updated by tag_success/tag_error nodes

// Greetings don't need admin notification unless it's a handoff
if (caseType === 'greeting' && action !== 'handoff') {
  notifyAdmins = false;
}
// Also suppress for unclear first attempts (customer might clarify next message)
if (caseType === 'unclear' && action !== 'handoff' && !pauseAutomation) {
  notifyAdmins = false;
}
if (commercialLead) {
  notifyAdmins = true;
}

const replyStatusLabel = {
  'generated': '🤖 Yanıt Hazırlandı',
  'handed_off': '📩 Uzmanına Aktarıldı',
  'suppressed_manual': '⏸️ Manuel Mod - Yanıt Gönderilmedi',
  'suppressed': '🔇 Yanıt Bastırıldı',
  'pending_retry': '🔁 Tekrar Denenecek'
};
const statusLabel = replyStatusLabel[replyStatus] || '📝 Yanıt Hazırlandı';

const escapedName = String(ctx.senderName || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
if (escapedName) reply = reply.replace(new RegExp(`^(Merhaba|Selam)\\s+${escapedName}\\s*(?:bey|hanım)?[,!:.]*\\s*`, 'i'), '$1, ');
reply = reply.replace(/\*\*(.+?)\*\*/g, '*$1*');
reply = reply.replace(/\s+/g, ' ').trim();

let reason = '';
if (action === 'handoff') reason = handoffReason || 'manual_review_required';
else if (caseType === 'partial_code') reason = partialSubType === 'bulk_request'
  ? 'bulk_purchase_intent'
  : 'missing_product_code_or_vehicle';
else if (caseType === 'exact_code_price_stock') reason = 'product_code_identified';
else if (caseType === 'exact_code_compatibility' && !vehicleComplete) reason = 'vehicle_info_incomplete';
else if (caseType === 'exact_code_compatibility') reason = 'vehicle_and_code_ready';
else if (caseType === 'cross_reference') reason = 'cross_reference_requested';
else if (caseType === 'greeting') reason = 'customer_greeting';
else reason = 'classified';

const missingFields = [];
if (caseType === 'partial_code' && partialSubType !== 'bulk_request' && normalizedCodes.length === 0) missingFields.push('productCode');
if (caseType === 'exact_code_compatibility' && !vehicleComplete) missingFields.push(...missingVehicleFields);
if (!yearMatch && !(caseType === 'partial_code' && partialSubType === 'bulk_request')) missingFields.push('year');

const safetyFlags = [];
if (invented.length > 0) safetyFlags.push('invented_code_blocked');
if (unsafeClaim) safetyFlags.push('unsafe_claim_rewritten');
if (confidence < 0.55) safetyFlags.push('low_confidence');

// Set fallbackType based on what triggered the fallback
if (handoffReason === 'unclear_intent') fallbackType = 'unclear_intent';
else if (retryAi) fallbackType = 'technical_failure';
else if (unsafeClaim) fallbackType = 'safety_replacement';

const codeText = normalizedCodes.length ? normalizedCodes.map(code => `• ${code}`).join('\n') : 'Belirtilmedi';
const vehicleText = vehicleStrings.length ? vehicleStrings.map(vehicle => `• ${vehicle}`).join('\n') : (extractedVehicle ? `• ${extractedVehicle}` : 'Belirtilmedi');
let title = '📩 YENİ TALEP';
let extraInfo = '';
const funnelStage =
  caseType === 'greeting' ? 'F1 Yakalama'
  : caseType === 'partial_code' ? 'F2 Nitelendirme'
  : caseType === 'cross_reference' ? 'F3 Değer'
  : ['exact_code_price_stock','exact_code_compatibility'].includes(caseType) ? 'F4 Dönüşüm'
  : ['complaint','return_complaint'].includes(intent) ? 'F5 Elde Tutma'
  : 'F1 Yakalama';
const upsellFlag = (caseType === 'exact_code_compatibility' && vehicleComplete) ? '\n📈 Upsell fırsatı: periyodik bakım seti' : '';
const bulkFlag = isBulkOrder ? `\n📦 Toplu sipariş: ${entities.quantity} adet — B2B fiyatlandırma değerlendirilebilir` : '';
const titleMap = {
  exact_code_price_stock: '📦 STOK/FİYAT SORGUSU',
  exact_code_compatibility: '🚗 UYUMLULUK SORGUSU',
  cross_reference: '🔄 MUADİL ARAMA',
  partial_code: '🔎 EKSİK BİLGİ',
  non_product: (() => {
    if (intent === 'return_complaint') return '🔄 İADE/DEĞİŞİM TALEBİ';
    if (intent === 'complaint') return '⚠️ MÜŞTERİ ŞİKAYETİ';
    if (intent === 'human_request') return '👤 TEMSİLCİ TALEBİ';
    return '📩 DESTEK TALEBİ';
  })(),
  greeting: '👋 SELAMLAMA',
  unclear: '❓ BELİRSİZ TALEP',
  other: '📩 YENİ TALEP'
};
title = titleMap[caseType] || '📩 YENİ TALEP';
if (hasVin) title = '🚗 ŞASİ NO İLE UYUMLULUK SORGUSU';
if (caseType === 'partial_code') {
  title = partialSubType === 'bulk_request' ? '💰 TOPLU ALIM TALEBİ'
    : partialSubType === 'incomplete_code' ? '🔎 EKSİK KOD'
    : partialSubType === 'vehicle_info_only' ? '🚗 ARAÇ BİLGİSİ GEREKLİ'
    : '🔎 EKSİK BİLGİ';
  extraInfo = partialSubType === 'bulk_request' ? '🤖 Toplu fiyat çalışması'
    : '🤖 Müşteriden bilgi istendi';
}
else if (action === 'handoff') extraInfo = handoffReason ? `⚠️ ${handoffReason}` : '';

let actionLine = '';
if (caseType === 'exact_code_price_stock' && action !== 'handoff') actionLine = '\n🎯 Beklenen Aksiyon: Stok & Fiyat Kontrolü';
else if (caseType === 'exact_code_compatibility' && !vehicleComplete) actionLine = '\n⏳ Eksik Bilgi: Araç detayı bekleniyor';
else if (caseType === 'cross_reference') actionLine = '\n🎯 Beklenen Aksiyon: Muadil Çapraz Referans Kontrolü';
else if (action === 'handoff') actionLine = '\n🎯 Beklenen Aksiyon: Manuel Müdahale';
else if (caseType === 'partial_code') actionLine = partialSubType === 'bulk_request'
  ? '\n🎯 Beklenen Aksiyon: Toplu fiyat teklifi hazırla'
  : '\n⏳ Müşteriden ek bilgi bekleniyor';
else if (intent === 'return_complaint') actionLine = '\n🎯 Beklenen Aksiyon: Şikayet/İade İşlemi';

const handoffLine = action === 'handoff'
  ? `\n🚦 Manuel Geçiş: Bu müşteri manuel incelemeye alındı. Sebep: ${handoffReason || 'manual_review_required'}`
  : '';

const messageCount = ctx.messageCount || 1;
const batchLabel = messageCount > 1 ? `\n📋 ${messageCount} mesaj birleştirildi` : '';

const adminMessage = `${title}\n👤 ${ctx.senderName} · ${ctx.senderNumber}${extraInfo ? `\n${extraInfo}` : ''}${actionLine}${handoffLine}${upsellFlag}${bulkFlag}\n🎯 Funnel: ${funnelStage}\n\n💬 Müşteri\n"${originalText}"\n\n${statusLabel}\n"${reply}"${handoffReason ? `\n\n⚠️ ${handoffReason}` : ''}`;
return { json: {
  ...ctx, intent, caseType, entities, cevap: reply, bildirim: adminMessage,
  notifyAdmins, replyCustomer: action !== 'ignore' && Boolean(reply), pauseAutomation,
  askVehicleInfo, expectsReply: askVehicleInfo || parsed.expectsReply === true,
  action, handoffReason, retryAi, reason, missingFields, safetyFlags, partialSubType,
  fallbackType,
  replyStatus, deliveryStatus,
  parseFailureCode: retryAi ? 'invalid_ai_json' : null,
  parseFailureMessage: retryAi ? 'AI output could not be parsed as valid JSON' : null,
  fingerprint: `${ctx.senderNumber}:${caseType}:${normalizedCodes.sort().join(',')}:${vehicleStrings.join(',')}`,
  rawOriginalText: originalText,
  schemaVersion: '13.6',
  templateKey: `${caseType}${partialSubType ? '_' + partialSubType : ''}_${action === 'handoff' ? 'handoff' : 'auto'}`,
  mergedMessageCount: ctx.messageCount || 1,
  mode: pauseAutomation ? 'manual' : 'automatic',
  priority: caseType === 'non_product' && intent === 'complaint' ? 'high'
    : caseType === 'non_product' && intent === 'return_complaint' ? 'high'
    : action === 'handoff' ? 'normal'
    : caseType === 'greeting' ? 'low'
    : 'normal',
  slaClass: caseType === 'non_product' && intent === 'complaint' ? 'complaint'
    : caseType === 'non_product' && intent === 'return_complaint' ? 'return'
    : caseType === 'exact_code_price_stock' ? 'sales_query'
    : caseType === 'exact_code_compatibility' ? 'compatibility'
    : caseType === 'cross_reference' ? 'cross_reference'
    : 'general',
  funnelStage,
  hasUpsellOpportunity: caseType === 'exact_code_compatibility' && vehicleComplete,
  isBulkOrder
} };
""".strip()


check_business_hours_js = r"""
const ctx = $json || {};
const tz = 'Europe/Istanbul';
const now = ctx.overrideNow ? new Date(ctx.overrideNow) : new Date();
const hour = Number(new Intl.DateTimeFormat('tr-TR', { hour: 'numeric', hour12: false, timeZone: tz }).format(now));
const minute = Number(new Intl.DateTimeFormat('tr-TR', { minute: 'numeric', timeZone: tz }).format(now));
const dayShort = now.toLocaleDateString('en-US', { weekday: 'short', timeZone: tz });
const dateKey = new Intl.DateTimeFormat('en-CA', { timeZone: tz }).format(now);
const year = dateKey.slice(0, 4);

// Load holidays from settings (jsonb)
const holidaysSetting = $('Load Holiday Settings').item.json || {};
const holidaysJson = holidaysSetting.holidays || {};
const holidaysForYear = holidaysJson[year] || [];
const HOLIDAYS = Array.isArray(holidaysForYear) ? holidaysForYear : [];

const BUSINESS_HOURS = { Mon: [9, 18], Tue: [9, 18], Wed: [9, 18], Thu: [9, 18], Fri: [9, 18], Sat: [9, 18], Sun: null };
const window = HOLIDAYS.includes(dateKey) ? null : BUSINESS_HOURS[dayShort];
const offHours = !Array.isArray(window) || hour < window[0] || hour >= window[1];
const nextBusinessOpenIso = (() => {
  if (!offHours) return null;
  const cursor = new Date(now.getTime());
  for (let i = 0; i < 14; i += 1) {
    const candidateDateKey = new Intl.DateTimeFormat('en-CA', { timeZone: tz }).format(cursor);
    const candidateDayShort = cursor.toLocaleDateString('en-US', { weekday: 'short', timeZone: tz });
    const candidateYear = candidateDateKey.slice(0, 4);
    const candidateHolidays = holidaysJson[candidateYear] || [];
    const candidateWindow = candidateHolidays.includes(candidateDateKey) ? null : BUSINESS_HOURS[candidateDayShort];
    if (Array.isArray(candidateWindow)) {
      if (candidateDateKey === dateKey && hour < candidateWindow[0]) {
        return new Date(`${candidateDateKey}T${String(candidateWindow[0]).padStart(2, '0')}:00:00+03:00`).toISOString();
      }
      if (candidateDateKey !== dateKey) {
        return new Date(`${candidateDateKey}T${String(candidateWindow[0]).padStart(2, '0')}:00:00+03:00`).toISOString();
      }
    }
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return null;
})();
const scenario = HOLIDAYS.includes(dateKey)
  ? 'holiday'
  : dayShort === 'Sun'
    ? 'sunday'
    : hour < 9
      ? 'early_morning'
      : 'evening';
const istanbulDay = { Mon: 'Pazartesi', Tue: 'Salı', Wed: 'Çarşamba', Thu: 'Perşembe', Fri: 'Cuma', Sat: 'Cumartesi', Sun: 'Pazar' }[dayShort] || dayShort;
const istanbulTime = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
return { json: {
  ...ctx,
  offHours,
  isHoliday: HOLIDAYS.includes(dateKey),
  scenario,
  istanbulDay,
  istanbulTime,
  nextAiAttemptAt: nextBusinessOpenIso,
  senderName: String(ctx.senderName || ctx.pushName || 'Değerli Müşterimiz'),
  senderNumber: String(ctx.senderNumber || ''),
  businessWindow: window,
} };
""".strip()


build_ooh_messages_js = r"""
const ctx = $('Check Business Hours').item.json || {};
const claim = $('Claim OOH Notification').item.json || {};
const senderName = String(claim.senderName || ctx.senderName || 'Değerli Müşterimiz');
const senderNumber = String(claim.senderNumber || ctx.senderNumber || '');
const scenario = String(claim.scenario || ctx.scenario || 'evening');
const istanbulDay = String(claim.istanbulDay || ctx.istanbulDay || '');
const istanbulTime = String(claim.istanbulTime || ctx.istanbulTime || '');
const isHoliday = ctx.isHoliday === true;
const cooldownCount = 0;
const sendCustomer = claim.claimed === true;
const managerPhoneA = String(claim.adminPhoneA || '');
const managerPhoneB = String(claim.adminPhoneB || '');
const managerTargets = [managerPhoneA, managerPhoneB].filter(Boolean);
const name = senderName || 'Değerli Müşterimiz';
const scenarioLabel = {
  sunday: 'Pazar (Tüm Gün Kapalı)',
  holiday: 'Resmi Tatil',
  early_morning: 'Sabah Erken (00:00-09:00)',
  evening: 'Akşam Mesai Dışı (18:00-24:00)',
}[scenario] || 'Bilinmiyor';

const templates = {
  sunday: `Merhaba 👋\n\nPazar günü bizi tercih ettiğiniz için teşekkür ederiz.\n\nOtoFiltre olarak Pazar günleri işletmemiz kapalıdır. Mesajınız kayıt altına alınmıştır ve Pazartesi sabahı 09:00 itibarıyla uzmanlarımız tarafından değerlendirilecektir.\n\n🕘 Mesai saatlerimiz:\nPazartesi – Cumartesi: 09:00 – 18:00\n\nAnlayışınız için teşekkür eder, iyi Pazarlar dileriz! 🙏\n— OtoFiltre Ekibi`,
  holiday: `Merhaba 👋\n\nResmi tatil günü bizi tercih ettiğiniz için teşekkür ederiz.\n\nBugün işletmemiz resmi tatil nedeniyle kapalıdır. Mesajınız kayıt altına alınmıştır; bir sonraki iş günü sabahı 09:00 itibarıyla uzman ekibimiz tarafından değerlendirilecektir.\n\n🕘 Mesai saatlerimiz:\nPazartesi – Cumartesi: 09:00 – 18:00 (Resmi tatiller hariç)\n\nAnlayışınız için teşekkür ederiz. 🙏\n— OtoFiltre Ekibi`,
  early_morning: `Merhaba 👋\n\nSabahın erken saatinde bize ulaştığınız için teşekkür ederiz.\n\nMesajınız alınmıştır. Ekibimiz bugün saat 09:00'da göreve başlayacak ve size en kısa sürede dönüş yapacaktır.\n\n🕘 Mesai saatlerimiz:\nPazartesi – Cumartesi: 09:00 – 18:00\n\nİyi günler dileriz! 🙏\n— OtoFiltre Ekibi`,
  evening: `Merhaba 👋\n\nMesajınız için teşekkür ederiz.\n\nŞu an (${istanbulTime}) işletmemiz mesai saatleri dışındadır. Mesajınız kayıt altına alınmıştır; yarın sabah 09:00 itibarıyla uzman ekibimiz tarafından değerlendirilecek ve size dönüş yapılacaktır.\n\n🕘 Mesai saatlerimiz:\nPazartesi – Cumartesi: 09:00 – 18:00\n\nBizi tercih ettiğiniz için teşekkür eder, anlayışınız için minnettarız. 🙏\n— OtoFiltre Ekibi`,
};

const customerMsg = templates[scenario] || templates.evening;
const managerMsg = `📋 *Mesai Dışı Müşteri Bildirimi*\n────────────────────\n👤 *Müşteri:* ${name}\n📱 *Numara:* +${senderNumber}\n🗓 *Zaman:* ${istanbulDay} ${istanbulTime} (İstanbul)\n⏰ *Durum:* ${scenarioLabel}\n────────────────────\n✅ Müşteriye otomatik bilgilendirme ${sendCustomer ? 'gönderilecek.' : 'cooldown nedeniyle atlandı.'}\n📥 Mesaj sisteme kaydedildi, iş saatinde işlenecek.\n\n💡 *Öneri:* Bir sonraki iş gününde 09:00'da bu müşteriyi öncelikli ele alın.\n\n— OtoFiltre Otomatik Sistem`;
const logSummary = sendCustomer
  ? 'customer notification queued'
  : 'customer notification skipped by cooldown';

return { json: {
  ...ctx,
  ...claim,
  senderName,
  senderNumber,
  scenario,
  istanbulDay,
  istanbulTime,
  isHoliday,
  cooldownCount,
  sendCustomer,
  customerMsg,
  managerMsg,
  managerPhoneA,
  managerPhoneB,
  managerTargets,
  oohLogId: String(claim.oohLogId || ''),
  oohClaimed: claim.claimed === true,
  customerSent: sendCustomer,
  managerSent: managerTargets.length > 0,
  logSummary,
  correlationId: String(ctx.correlationId || claim.correlationId || ''),
} };
""".strip()




prepare_ai_failure_js = r"""
let ctx = $json || {};
if (!ctx.senderNumber || !ctx.batchToken) {
  try { ctx = { ...$('Store Context').item.json, ...ctx }; } catch (_) {}
}
return { json: {
  senderNumber: String(ctx.senderNumber || ''), batchToken: String(ctx.batchToken || ''),
  errorCode: String(ctx.parseFailureCode || ctx.error?.code || 'ai_error'),
  errorMessage: String(ctx.parseFailureMessage || ctx.error?.message || ctx.message || 'AI execution failed').slice(0, 2000),
  correlationId: String(ctx.correlationId || '')
} };
""".strip()


prepare_batch_completion_failure_js = r"""
let ctx = $json || {};
if (!ctx.senderNumber || !ctx.batchToken) {
  try { ctx = { ...$('Store Context').item.json, ...ctx }; } catch (_) {}
}
return { json: {
  senderNumber: String(ctx.senderNumber || ''),
  batchToken: String(ctx.batchToken || ''),
  parseFailureCode: String(ctx.completionFailureCode || 'batch_completion_failed'),
  parseFailureMessage: String(ctx.completionFailureMessage || 'complete_ai_batch returned false').slice(0, 2000),
  correlationId: String(ctx.correlationId || '')
} };
""".strip()


prepare_delivery_js = r"""
const row = $json || {};

let payload = {};
try {
  payload = typeof row.payload === 'string'
    ? JSON.parse(row.payload)
    : (row.payload || {});
} catch (error) {
  return {
    json: {
      validDelivery: false,
      deliveryId: String(row.id || ''),
      correlationId: String(row.correlation_id || row.correlationId || ''),
      validationError: 'invalid_payload_json'
    }
  };
}

const deliveryId = String(row.id || '');
const batchToken = String(row.batch_token || row.batchToken || '');
const correlationId = String(row.correlation_id || row.correlationId || '');
const channel = String(row.channel || '');
const rawDestination = String(row.destination || payload.number || '').trim();
const isLid = rawDestination.toLowerCase().endsWith('@lid');
let destination = isLid
  ? rawDestination.replace(/[^0-9@a-zA-Z._-]/g, '').replace(/@lid$/i, '@lid')
  : rawDestination.replace(/[^0-9]/g, '');

if (!isLid) {
  if (destination.startsWith('0090') && destination.length === 14) {
    destination = destination.slice(2);
  } else if (destination.startsWith('0') && destination.length === 11 && destination[1] === '5') {
    destination = '90' + destination.slice(1);
  } else if (destination.length === 10 && destination.startsWith('5')) {
    destination = '90' + destination;
  }
}

const text = String(payload.text || '').trim();

const uuidOk =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    .test(deliveryId);

const destinationOk = /^[1-9][0-9]{9,14}$/.test(destination)
  || /^[0-9]{5,20}@lid$/i.test(destination);
const textOk = text.length > 0 && text.length <= 4096;
const channelOk = ['customer', 'phone_a', 'phone_b'].includes(channel);

const errors = [];
if (!uuidOk) errors.push('invalid_delivery_id');
if (!destinationOk) errors.push('invalid_destination');
if (!textOk) errors.push('invalid_text');
if (!channelOk) errors.push('invalid_channel');

return {
  json: {
    deliveryId,
    batchToken,
    channel,
    senderNumber: String(row.sender_number || row.senderNumber || ''),
    destination,
    text,
    correlationId,
    validDelivery: errors.length === 0,
    validationError: errors.join(','),
    body: {
      number: destination,
      text
    }
  }
};
""".strip()


tag_success_js = r"""
const ctx = $('Prepare Delivery').item.json;
const providerId = String($json?.key?.id || $json?.messageId || $json?.id || '');
const success = providerId.length > 0;
return { json: { ...ctx, success, providerId, errorMessage: success ? '' : 'missing_provider_message_id' } };
""".strip()


tag_error_js = r"""
const ctx = $('Prepare Delivery').item.json;
const errorMessage = String($json?.error?.message || $json?.message || 'Evolution API request failed').slice(0, 2000);
return { json: { ...ctx, success: false, providerId: '', errorMessage } };
""".strip()


nodes = [
    {
        "parameters": {"httpMethod": "POST", "path": "evolution-webhook", "responseMode": "responseNode", "options": {}},
        "id": node_id("Webhook1"), "name": "Webhook1", "type": "n8n-nodes-base.webhook",
        "typeVersion": 2, "position": [120, 300], "webhookId": "d4e5f6a7-b8c9-4d0e-8f1a-2b3c4d5e6f7a",
    },
    code_node("Validate Webhook Secret", validate_webhook_secret_js, [560, 160]),
    if_node("Webhook Auth", "={{ $json.authorized === true }}", [780, 160]),
    postgres_node(
        "Load Admin Filter Settings",
        "SELECT COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_a'), '') AS \"adminPhoneA\", COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_b'), '') AS \"adminPhoneB\"",
        "={{ [] }}",
        [1000, 160],
    ),
    code_node("Apply Admin Number Filter", apply_admin_number_filter_js, [1220, 160]),
    if_node("Is Admin Number?", "={{ $json.isAdminNumber === true }}", [1440, 160]),
    {
        "parameters": {"respondWith": "json", "responseBody": "={{ { accepted: true, ignored: true, adminFiltered: true, correlationId: $json.correlationId || '' } }}", "options": {"responseCode": 202}},
        "id": node_id("Respond Admin Filtered"), "name": "Respond Admin Filtered", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4, "position": [1660, 80],
    },
    {
        "parameters": {"respondWith": "json", "responseBody": "={{ { accepted: false, error: 'unauthorized', correlationId: $json.correlationId || '' } }}", "options": {"responseCode": 401}},
        "id": node_id("Respond Unauthorized"), "name": "Respond Unauthorized", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4, "position": [560, 440],
    },
    code_node("Normalize Payload", normalize_js, [340, 260]),
    if_node("Valid Event?", "={{ $json.valid === true }}", [560, 260]),
    postgres_node(
        "Load Holiday Settings",
        "SELECT value_jsonb AS holidays FROM whatsapp_ai.settings WHERE key = 'holidays'",
        "={{ [] }}",
        [780, 160],
    ),
    code_node("Check Business Hours", check_business_hours_js, [780, 260]),
    postgres_node(
        "Claim OOH Notification",
        """WITH candidate AS (
    SELECT b.sender_number
    FROM whatsapp_ai.batches b
    WHERE b.sender_number = $1
      AND b.status = 'pending'
      AND jsonb_array_length(b.pending_messages) > 0
      AND b.first_message_at <= clock_timestamp() - INTERVAL '120 seconds'
      AND NOT EXISTS (
          SELECT 1
          FROM whatsapp_ai.ooh_log l
          WHERE l.sender_number = b.sender_number
            AND l.created_at > clock_timestamp() - INTERVAL '8 hours'
            AND l.customer_sent = true
      )
      AND NOT EXISTS (
          SELECT 1
          FROM whatsapp_ai.ooh_log l
          WHERE l.sender_number = b.sender_number
            AND l.created_at > clock_timestamp() - INTERVAL '10 minutes'
            AND l.customer_sent = false
      )
    ORDER BY b.first_message_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
), claimed AS (
    INSERT INTO whatsapp_ai.ooh_log(sender_number, sender_name, scenario, istanbul_day, istanbul_time, customer_sent, manager_sent, correlation_id)
    SELECT $1, $2, $3, $4, $5, false, false, $6
    FROM candidate
    ON CONFLICT (sender_number) DO NOTHING
    RETURNING id
)
SELECT EXISTS(SELECT 1 FROM claimed) AS claimed,
       (SELECT id FROM claimed LIMIT 1) AS \"oohLogId\",
       $1::text AS \"senderNumber\",
       $2::text AS \"senderName\",
       $3::text AS scenario,
       $4::text AS \"istanbulDay\",
       $5::text AS \"istanbulTime\",
       $6::text AS \"correlationId\",
       COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_a'), '') AS \"adminPhoneA\",
       COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_b'), '') AS \"adminPhoneB\"""",
        "={{ [ $('Normalize Payload').item.json.senderNumber, $('Normalize Payload').item.json.senderName, $('Check Business Hours').item.json.scenario, $('Check Business Hours').item.json.istanbulDay, $('Check Business Hours').item.json.istanbulTime, $('Normalize Payload').item.json.correlationId || '' ] }}",
        [1000, 520],
    ),
    if_node("Is Off Hours?", "={{ $('Check Business Hours').item.json.offHours === true }}", [1220, 260]),
    wait_node("Wait OOH 120 Seconds", 2, "minutes", [1440, 520]),
    code_node("Build OOH Messages", build_ooh_messages_js, [1440, 260]),
    if_node("OOH Claim Won?", "={{ $json.claimed === true }}", [1660, 520]),
    {
        "parameters": {
            "method": "POST", "url": f"{os.environ.get('EVOLUTION_API_URL', 'https://evo.filtreoto.online')}/message/sendText/otofiltre",
            "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: $json.senderNumber, text: $json.customerMsg }) }}",
            "options": {"timeout": 15000},
        },
        "id": node_id("Send OOH to Customer"), "name": "Send OOH to Customer", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [1880, 120], "onError": "continueErrorOutput",
        "continueOnFail": True,
        "alwaysOutputData": True,
        "credentials": {"httpHeaderAuth": {"id": EVOLUTION_ID, "name": EVOLUTION_NAME}},
    },
    postgres_node(
        "Enqueue Manager OOH Alert",
        "SELECT whatsapp_ai.enqueue_ooh_manager_alert($1::uuid, $2) AS queued",
        "={{ [ $('Build OOH Messages').item.json.oohLogId, $('Build OOH Messages').item.json.managerMsg ] }}",
        [2100, 120],
    ),
    postgres_node(
        "Log OOH Event",
        "UPDATE whatsapp_ai.ooh_log SET customer_sent = $2 WHERE id = $1::uuid RETURNING id",
        "={{ [ $('Build OOH Messages').item.json.oohLogId, $('Build OOH Messages').item.json.customerSent ] }}",
        [2540, 260],
    ),
    if_node("Rate Limit Exceeded?", "={{ $json.rateLimitExceeded === true }}", [780, 260]),
    {
        "parameters": {"respondWith": "json", "responseBody": "={{ { accepted: true, ignored: true, rateLimited: true, correlationId: $json.correlationId || '' } }}", "options": {"responseCode": 202}},
        "id": node_id("Respond Rate Limited"), "name": "Respond Rate Limited", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4, "position": [1000, 520],
    },
    {
        "parameters": {"respondWith": "json", "responseBody": "={{ { accepted: true, ignored: true, correlationId: $json.correlationId || '' } }}", "options": {"responseCode": 202}},
        "id": node_id("Respond Ignored"), "name": "Respond Ignored", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4, "position": [1000, 420],
    },
    {
        **postgres_node(
            "Ingest Message",
            "SELECT * FROM whatsapp_ai.ingest_message($1,$2,$3,$4::jsonb,$5,$6,$7,$8)",
            "={{ [ $('Normalize Payload').item.json.messageId, $('Normalize Payload').item.json.senderNumber, $('Normalize Payload').item.json.senderName, JSON.stringify({ text: $('Normalize Payload').item.json.message.text, type: $('Normalize Payload').item.json.message.type, timestamp: $('Normalize Payload').item.json.message.timestamp, mediaUrl: $('Normalize Payload').item.json.message.mediaUrl, mimetype: $('Normalize Payload').item.json.message.mimetype, isMediaMessage: $('Normalize Payload').item.json.message.isMediaMessage, mediaType: $('Normalize Payload').item.json.message.mediaType, fromMe: $('Normalize Payload').item.json.fromMe, command: $('Normalize Payload').item.json.command, rawJid: $('Normalize Payload').item.json.rawJid, senderNumber: $('Normalize Payload').item.json.senderNumber, senderName: $('Normalize Payload').item.json.senderName, messageId: $('Normalize Payload').item.json.messageId, correlationId: $('Normalize Payload').item.json.correlationId, nextAiAttemptAt: $('Check Business Hours').item.json.nextAiAttemptAt || null }), $('Normalize Payload').item.json.command, $('Normalize Payload').item.json.webhookToken, $('Normalize Payload').item.json.authSource, $('Check Business Hours').item.json.nextAiAttemptAt || null ] }}",
            [1000, 240],
        ),
        "onError": "continueErrorOutput",
    },
    {
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ { accepted: false, retryable: true, error: 'temporary_ingest_failure', correlationId: $json.correlationId || '' } }}",
            "options": {"responseCode": 503},
        },
        "id": node_id("Respond 503"), "name": "Respond 503", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4,
        "position": [1220, 440],
    },
    code_node(
        "Prepare Ingest Failure",
        "const ctx = $json || {};\nconst corrId = String(ctx.correlationId || '');\nreturn { json: { accepted: false, retryable: true, error: 'temporary_ingest_failure', correlationId: corrId || ('fallback-' + Date.now()) } };",
        [1120, 440],
    ),
    {
        "parameters": {"respondWith": "json", "responseBody": "={{ { accepted: true, action: $json.action || 'queued', correlationId: $json.correlationId || '' } }}", "options": {"responseCode": 202}},
        "id": node_id("Respond Accepted"), "name": "Respond Accepted", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4, "position": [1220, 240],
    },
    {
        "parameters": {"rule": {"interval": [{"field": "seconds", "secondsInterval": 15}]}},
        "id": node_id("Schedule Trigger"), "name": "Schedule Trigger", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [120, 720],
    },
    postgres_node("OpenAI Circuit Gate", "SELECT whatsapp_ai.circuit_allows('openai') AS allowed", "={{ [] }}", [340, 620]),
    if_node("OpenAI Circuit Open?", "={{ $json.allowed === true }}", [560, 620]),
    postgres_node(
        "Claim Ready Batches",
        """SELECT claimed.*, COALESCE((
    SELECT jsonb_agg(jsonb_build_object('role', recent.role, 'content', recent.content) ORDER BY recent.created_at)
    FROM (
        SELECT role, content, created_at
        FROM whatsapp_ai.chat_memory
        WHERE session_id = claimed.sender_number
        ORDER BY created_at DESC
        LIMIT 20
    ) recent
), '[]'::jsonb) AS chat_memory
FROM whatsapp_ai.claim_ready_batches(10) claimed""",
        "={{ [] }}",
        [780, 620],
    ),
    code_node("Store Context", store_context_js, [1000, 620]),
    {
        "parameters": {"promptType": "define", "text": "={{ $json._prompt }}", "options": {"systemMessage": system_prompt}},
        "id": node_id("AI Agent"), "name": "AI Agent", "type": "@n8n/n8n-nodes-langchain.agent", "typeVersion": 3.1,
        "position": [1220, 620], "onError": "continueErrorOutput",
    },
    {
        "parameters": {"model": {"__rl": True, "value": "gpt-5.4", "mode": "list", "cachedResultName": "gpt-5.4"}, "builtInTools": {}, "options": {"temperature": 0.1, "maxTokens": 700}},
        "id": node_id("OpenAI Chat Model1"), "name": "OpenAI Chat Model1", "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi", "typeVersion": 1.3,
        "position": [1140, 840], "credentials": {"openAiApi": {"id": OPENAI_ID, "name": OPENAI_NAME}},
    },
    code_node("Parse AI Output", parse_ai_js, [1440, 560]),
    if_node("AI Output Valid?", "={{ $json.retryAi !== true }}", [1660, 560]),
    postgres_node(
        "Complete AI Batch",
        "SELECT whatsapp_ai.complete_ai_batch($1,$2::uuid,$3,$4,$5,$6,$7,$8,$9,$10) AS completed, whatsapp_ai.record_service_result('openai',true,NULL) AS circuit_state",
        "={{ [ $json.senderNumber, $json.batchToken, $json.cevap, $json.bildirim, $json.notifyAdmins, $json.replyCustomer, $json.pauseAutomation, $json.fingerprint, $json.caseType, $json.correlationId || '' ] }}",
        [2760, 520],
    ),
    if_node("AI Batch Completed?", "={{ $json.completed === true }}", [2980, 520]),
    postgres_node(
        "Persist Chat Memory",
        """WITH user_messages AS (
    SELECT $1::text AS session_id, 'user'::text AS role,
           left(COALESCE(message->>'text', ''), 4000) AS content,
           COALESCE(NULLIF(message->>'id', ''), md5(message::text)) AS source_key
    FROM jsonb_array_elements($2::jsonb) AS message
    WHERE COALESCE(message->>'text', '') <> ''
), assistant_message AS (
    SELECT $1::text AS session_id, 'assistant'::text AS role,
           left($4::text, 4000) AS content,
           'assistant:' || $3::text AS source_key
    WHERE COALESCE($4::text, '') <> ''
), memory_rows AS (
    SELECT * FROM user_messages
    UNION ALL
    SELECT * FROM assistant_message
)
INSERT INTO whatsapp_ai.chat_memory(session_id, role, content, source_key)
SELECT session_id, role, content, source_key
FROM memory_rows
ON CONFLICT (session_id, role, source_key) DO NOTHING
RETURNING id""",
        "={{ [ $('Parse AI Output').item.json.senderNumber, JSON.stringify($('Store Context').item.json.messages || []), $('Parse AI Output').item.json.batchToken, $('Parse AI Output').item.json.cevap || '' ] }}",
        [3200, 520],
    ),
    code_node("Prepare AI Failure", prepare_ai_failure_js, [1880, 700]),
    code_node("Prepare Batch Completion Failure", prepare_batch_completion_failure_js, [3180, 700]),
    postgres_node(
        "Record AI Failure",
        "SELECT whatsapp_ai.record_ai_failure($1,$2::uuid,$3,$4,$5) AS result, whatsapp_ai.record_service_result('openai',false,$3) AS circuit_state",
        "={{ [ $json.senderNumber, $json.batchToken, $json.errorCode, $json.errorMessage, $json.correlationId || '' ] }}",
        [2100, 700],
    ),
    postgres_node("Evolution Circuit Gate", "SELECT whatsapp_ai.circuit_allows('evolution') AS allowed", "={{ [] }}", [340, 820]),
    if_node("Evolution Circuit Open?", "={{ $json.allowed === true }}", [560, 820]),
    postgres_node("Claim Deliveries", "SELECT * FROM whatsapp_ai.claim_deliveries(20)", "={{ [] }}", [780, 820]),
    code_node("Prepare Delivery", prepare_delivery_js, [560, 820]),
    if_node("Delivery Valid?", "={{ $json.validDelivery === true }}", [780, 820]),
    {
        "parameters": {
            "method": "POST", "url": f"{os.environ.get('EVOLUTION_API_URL', 'https://evo.filtreoto.online')}/message/sendText/otofiltre",
            "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify($json.body) }}", "options": {"timeout": 15000},
        },
        "id": node_id("Send Delivery"), "name": "Send Delivery", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [1000, 820], "onError": "continueErrorOutput",
        "credentials": {"httpHeaderAuth": {"id": EVOLUTION_ID, "name": EVOLUTION_NAME}},
    },
    code_node("Tag Delivery Validation Error", """
const ctx = $json || {};
return {
  json: {
    ...ctx,
    success: false,
    providerId: '',
    errorMessage: `delivery_validation:${ctx.validationError || 'unknown'}`
  }
};
""", [1000, 920]),
    code_node("Tag Delivery Success", tag_success_js, [1220, 800]),
    code_node("Tag Delivery Error", tag_error_js, [1000, 920]),
    postgres_node(
        "Record Delivery Result",
        "SELECT whatsapp_ai.record_delivery_result($1::uuid,$2,$3,$4) AS result, whatsapp_ai.record_service_result('evolution',$2,CASE WHEN $2 THEN NULL ELSE 'delivery_error' END) AS circuit_state",
        "={{ [ $json.deliveryId, $json.success, $json.providerId || null, $json.errorMessage || null ] }}",
        [1220, 840],
    ),
    postgres_node(
        "Run Stale Batch Monitor",
        "SELECT whatsapp_ai.run_stale_batch_monitor() AS result",
        "={{ [] }}",
        [340, 920],
    ),
]


for node in nodes:
    name = node.get("name")
    if name in {
        "Ingest Message",
        "Claim Ready Batches",
        "Claim Deliveries",
        "Complete AI Batch",
        "Record AI Failure",
        "Record Delivery Result",
        "OpenAI Circuit Gate",
        "Evolution Circuit Gate",
        "Claim OOH Notification",
        "Load Admin Filter Settings",
        "Load Holiday Settings",
        "Log OOH Event",
        "Run Stale Batch Monitor",
        "Persist Chat Memory",
    }:
        node["retryOnFail"] = True
        node["maxTries"] = 3
        node["waitBetweenTries"] = 2000

position_overrides = {
    "Check Business Hours": [784, 420],
    "Load Holiday Settings": [780, 160],
    "Claim OOH Notification": [1680, 620],
    "Is Off Hours?": [1232, 420],
    "Wait OOH 120 Seconds": [1456, 620],
    "Build OOH Messages": [2128, 420],
    "OOH Claim Won?": [1904, 620],
    "Send OOH to Customer": [1904, 340],
    "Enqueue Manager OOH Alert": [2128, 420],
    "Log OOH Event": [2576, 420],
    "Evolution Circuit Gate": [352, 1040],
    "Run Stale Batch Monitor": [340, 1040],
    "Evolution Circuit Open?": [560, 1040],
    "Claim Deliveries": [784, 1040],
    "Prepare Delivery": [1008, 1040],
    "Delivery Valid?": [1232, 1040],
    "Send Delivery": [1456, 1040],
    "Tag Delivery Success": [1680, 960],
    "Tag Delivery Error": [1680, 1088],
    "Tag Delivery Validation Error": [1456, 1216],
    "Record Delivery Result": [1904, 1040],
}
for node in nodes:
    position = position_overrides.get(node.get("name"))
    if position:
        node["position"] = position


connections = {
    "Webhook1": {"main": [[edge("Normalize Payload")]]},
    "Normalize Payload": {"main": [[edge("Validate Webhook Secret")]]},
    "Validate Webhook Secret": {"main": [[edge("Webhook Auth")]]},
    "Webhook Auth": {"main": [[edge("Load Admin Filter Settings")], [edge("Respond Unauthorized")]]},
    "Load Admin Filter Settings": {"main": [[edge("Apply Admin Number Filter")] ]},
    "Apply Admin Number Filter": {"main": [[edge("Is Admin Number?")]]},
    "Is Admin Number?": {"main": [[edge("Respond Admin Filtered")], [edge("Valid Event?")]]},
    "Valid Event?": {"main": [[edge("Load Holiday Settings")], [edge("Respond Ignored")]]},
    "Load Holiday Settings": {"main": [[edge("Check Business Hours")]]},
    "Check Business Hours": {"main": [[edge("Rate Limit Exceeded?")]]},
    "Is Off Hours?": {"main": [[edge("Wait OOH 120 Seconds")], []]},
    "Wait OOH 120 Seconds": {"main": [[edge("Claim OOH Notification")]]},
    "Claim OOH Notification": {"main": [[edge("OOH Claim Won?")]]},
    "OOH Claim Won?": {"main": [[edge("Build OOH Messages")], []]},
    "Build OOH Messages": {"main": [[edge("Send OOH to Customer")]]},
    "Send OOH to Customer": {"main": [[edge("Enqueue Manager OOH Alert")], [edge("Enqueue Manager OOH Alert")]]},
    "Enqueue Manager OOH Alert": {"main": [[edge("Log OOH Event")]]},
    "Log OOH Event": {"main": [[]]},
    "Rate Limit Exceeded?": {"main": [[edge("Respond Rate Limited")], [edge("Ingest Message")]]},
    "Ingest Message": {"main": [[edge("Respond Accepted"), edge("Is Off Hours?")], [edge("Prepare Ingest Failure")]]},
    "Respond Accepted": {"main": [[]]},
    "Prepare Ingest Failure": {"main": [[edge("Respond 503")]]},
    "Schedule Trigger": {"main": [[edge("OpenAI Circuit Gate"), edge("Evolution Circuit Gate"), edge("Run Stale Batch Monitor")]]},
    "OpenAI Circuit Gate": {"main": [[edge("OpenAI Circuit Open?")]]},
    "OpenAI Circuit Open?": {"main": [[edge("Claim Ready Batches")], []]},
    "Claim Ready Batches": {"main": [[edge("Store Context")]]},
    "Store Context": {"main": [[edge("AI Agent")]]},
    "AI Agent": {"main": [[edge("Parse AI Output")], [edge("Prepare AI Failure")]]},
    "Parse AI Output": {"main": [[edge("AI Output Valid?")]]},
    "AI Output Valid?": {"main": [[edge("Complete AI Batch")], [edge("Prepare AI Failure")]]},
    "Complete AI Batch": {"main": [[edge("AI Batch Completed?")]]},
    "AI Batch Completed?": {"main": [[edge("Persist Chat Memory")], [edge("Prepare Batch Completion Failure")]]},
    "Persist Chat Memory": {"main": [[]]},
    "Prepare AI Failure": {"main": [[edge("Record AI Failure")]]},
    "Prepare Batch Completion Failure": {"main": [[edge("Record AI Failure")]]},
    "OpenAI Chat Model1": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
    "Evolution Circuit Gate": {"main": [[edge("Evolution Circuit Open?")]]},
    "Evolution Circuit Open?": {"main": [[edge("Claim Deliveries")], []]},
    "Claim Deliveries": {"main": [[edge("Prepare Delivery")]]},
    "Prepare Delivery": {"main": [[edge("Delivery Valid?")]]},
    "Delivery Valid?": {"main": [[edge("Send Delivery")], [edge("Tag Delivery Validation Error")]]},
    "Send Delivery": {"main": [[edge("Tag Delivery Success")], [edge("Tag Delivery Error")]]},
    "Tag Delivery Success": {"main": [[edge("Record Delivery Result")]]},
    "Tag Delivery Error": {"main": [[edge("Record Delivery Result")]]},
    "Tag Delivery Validation Error": {"main": [[edge("Record Delivery Result")]]},
}


workflow = {
    "name": "WhatsApp AI - v13 PostgreSQL Outbox",
    "nodes": nodes,
    "connections": connections,
    "settings": {
        "executionOrder": "v1", "timezone": "Europe/Istanbul",
        "saveDataErrorExecution": "all", "saveDataSuccessExecution": "all",
        "saveExecutionProgress": True, "executionTimeout": 600,
    },
    "staticData": {"node:Schedule Trigger": {"recurrenceRules": []}, "global": {}},
    "pinData": {}, "active": False,
}


def check_javascript():
    checks = []
    for node in nodes:
        code = node.get("parameters", {}).get("jsCode")
        if code:
            checks.append((node["name"], code))
    for name, code in checks:
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
            handle.write("async function __check__() {\n" + code + "\n}\n")
            path = handle.name
        try:
            result = subprocess.run(["node", "--check", path], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(f"JavaScript syntax error in {name}: {result.stderr.strip()}")
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    check_javascript()
    OUTPUT.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT.name}: {len(nodes)} nodes, {len(connections)} connection sources")
    print("JavaScript syntax checks: PASS")
