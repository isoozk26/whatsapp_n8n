#!/usr/bin/env python3
"""Build the PostgreSQL-backed WhatsApp AI n8n workflow."""
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "workflow.json"
POSTGRES_ID = os.environ.get("N8N_POSTGRES_CREDENTIAL_ID", "whatsapp-state-postgres")
POSTGRES_NAME = os.environ.get("N8N_POSTGRES_CREDENTIAL_NAME", "WhatsApp State PostgreSQL")
EVOLUTION_ID = os.environ.get("N8N_EVOLUTION_CREDENTIAL_ID", "evolution-api")
EVOLUTION_NAME = os.environ.get("N8N_EVOLUTION_CREDENTIAL_NAME", "Evolution API")
OPENAI_ID = os.environ.get("N8N_OPENAI_CREDENTIAL_ID", "3M52tD49lJ35vXdO")
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


normalize_js = r"""
const root = $json || {};
const payload = root.body?.body?.data || root.body?.data || null;
const queryToken = String(root.query?.token || '');
const rawJid = String(payload?.key?.remoteJid || '');
const senderNumber = rawJid.replace(/@s\.whatsapp\.net$|@g\.us$|@lid$/g, '');
const text = String(payload?.message?.conversation
  || payload?.message?.extendedTextMessage?.text
  || payload?.message?.imageMessage?.caption
  || (payload?.message?.imageMessage ? '[Medya]' : '')).trim();
const fromMe = payload?.key?.fromMe === true;
const messageId = String(payload?.key?.id || '');
const isGroup = rawJid.endsWith('@g.us');
const isBroadcast = rawJid.endsWith('@broadcast');
const authorizedCommand = fromMe && ['++', '--'].includes(text);
const command = authorizedCommand ? (text === '++' ? 'pause' : 'resume') : null;
const valid = Boolean(payload && messageId && senderNumber && !isGroup && !isBroadcast && (!fromMe || command));
const message = {
  id: messageId, text: text || '[Medya]',
  type: payload?.message?.imageMessage ? 'image' : 'text',
  timestamp: Date.now(), mediaUrl: payload?.message?.imageMessage?.url || null,
  mimetype: payload?.message?.imageMessage?.mimetype || null
};
return { json: {
  valid, queryToken, senderNumber, senderName: String(payload?.pushName || senderNumber),
  messageId, fromMe, command, rawJid, message,
  commandMessageId: messageId, commandRemoteJid: rawJid,
  commandParticipant: String(payload?.key?.participant || '')
} };
""".strip()


store_context_js = r"""
const row = $json || {};
const messages = Array.isArray(row.messages) ? row.messages : [];
const allMessagesText = String(row.all_messages_text || '');
const detectedCodes = [...new Set((allMessagesText.toUpperCase().match(/\b[A-Z]{1,3}[ -]\d{2,}(?:(?:[/. -])[A-Z0-9]{1,8}){0,3}\b/g) || [])
  .map(x => x.trim()).filter(x => /\d/.test(x)))].slice(0, 20);
return { json: {
  senderNumber: String(row.sender_number || ''), senderName: String(row.sender_name || row.sender_number || ''),
  batchToken: String(row.batch_token || ''), messageCount: Number(row.message_count || messages.length),
  allMessagesText, detectedCodes, aiAttemptCount: Number(row.ai_attempt_count || 0),
  assigneeName: String(row.assignee_name || 'İsmail Özkaracan'),
  _prompt: `Müşteri mesajları:\n${allMessagesText}\n\nYalnız tanımlı JSON şemasında cevap ver.`
} };
""".strip()


system_prompt = """Sen otomotiv filtre satışı için güvenli bilgi çıkarımı yapan bir asistansın.
Yalnız JSON üret. Şema:
{"intent":"price_stock|compatibility|cross_reference|vehicle_search|return_complaint|greeting|unclear|other","caseType":"exact_code_price_stock|exact_code_compatibility|cross_reference|partial_code|vehicle_based_search|non_product|greeting|unclear|other","entities":{"productCodes":[],"vehicles":[],"preferredBrands":[],"quantity":"Belirtilmedi"},"replyDraft":"","confidence":0.0,"expectsReply":false}
Fiyat, stok, kargo veya uyumluluk doğrulanmış gibi gösterme. Müşterinin yazmadığı ürün kodunu üretme. Eksik araç bilgisinde motor hacmi ve beygir veya şasi iste. Şikayet, iade ve insan talebini non_product olarak sınıflandır."""


parse_ai_js = r"""
const current = $json || {};
const ctx = $('Store Context').item.json;
const raw = current.output ?? current.aiResult ?? current;
let parsed;
try {
  parsed = typeof raw === 'object'
    ? raw
    : JSON.parse(String(raw).replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim());
} catch (error) {
  parsed = { intent: 'unclear', caseType: 'unclear', entities: {}, confidence: 0, _parseError: true };
}

const allowed = new Set(['exact_code_price_stock','exact_code_compatibility','cross_reference','partial_code','vehicle_based_search','non_product','greeting','unclear','other']);
const originalText = String(ctx.allMessagesText || '');
const plainText = originalText.replace(/^\s*\d+\.\s*(?:\[[^\]]+\]\s*)?/, '').trim();
const textUpper = plainText.toLocaleUpperCase('tr-TR');
let intent = String(parsed.intent || 'other');
let caseType = String(parsed.caseType || 'other');
let entities = parsed.entities && typeof parsed.entities === 'object' ? parsed.entities : {};
let confidence = typeof parsed.confidence === 'number' ? parsed.confidence : Number(parsed.confidence?.caseType || 0);
let reply = String(parsed.replyDraft || '').trim();
let pauseAutomation = false;
let notifyAdmins = false;
let action = 'reply';
let handoffReason = '';
let askVehicleInfo = false;
let retryAi = false;

const filterRequest = /\b(yağ|yag|hava|yakıt|yakit|polen|kabin|şanzıman|sanziman)\s+filtresi?\b|\bfiltre\b/i.test(plainText);
const yearMatch = plainText.match(/\b(19\d{2}|20\d{2})\b/);
const brands = ['Fiat','Renault','Ford','Volkswagen','VW','Opel','Peugeot','Citroen','Toyota','Honda','Hyundai','Kia','Mercedes','BMW','Audi','Skoda','Seat','Dacia','Nissan'];
const brand = brands.find(item => new RegExp(`\\b${item}\\b`, 'i').test(plainText));
let extractedVehicle = '';
if (brand) {
  const afterBrand = plainText.slice(plainText.toLocaleLowerCase('tr-TR').indexOf(brand.toLocaleLowerCase('tr-TR')) + brand.length);
  const modelPart = afterBrand.split(/\b(?:19\d{2}|20\d{2})\b/)[0]
    .replace(/\b(?:yağ|yag|hava|yakıt|yakit|polen|kabin|filtre|filtresi|arıyorum|ariyorum|için|icin)\b/gi, ' ')
    .replace(/[^\p{L}\p{N}.-]+/gu, ' ').trim().split(/\s+/).slice(0, 3).join(' ');
  extractedVehicle = [brand === 'VW' ? 'Volkswagen' : brand, modelPart, yearMatch?.[1] || ''].filter(Boolean).join(' ').trim();
}

const vehicleRequestDetected = filterRequest && Boolean(brand || yearMatch);
if (vehicleRequestDetected && ['other','unclear','vehicle_based_search'].includes(caseType)) {
  caseType = 'vehicle_based_search';
  intent = 'vehicle_search';
}
const deterministicCase = vehicleRequestDetected || (Array.isArray(ctx.detectedCodes) && ctx.detectedCodes.length > 0)
  || ['exact_code_price_stock','exact_code_compatibility','cross_reference','partial_code','vehicle_based_search','greeting','non_product'].includes(caseType);

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
const vehicleBlob = `${plainText} ${vehicleStrings.join(' ')}`;
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
const plausibleCode = /^[A-Z]{1,3}[ -]\d{2,}(?:(?:[/. -])[A-Z0-9]{1,8}){0,3}$/i;
const normalizedCodes = codes.map(c => String(c?.code || c?.raw || c || '').trim())
  .filter(code => plausibleCode.test(code));
entities.productCodes = normalizedCodes.map(code => ({ code }));
if (normalizedCodes.length > 0 && ['other','unclear','partial_code','vehicle_based_search'].includes(caseType)) {
  caseType = 'exact_code_price_stock';
  intent = 'price_stock';
} else if (normalizedCodes.length === 0 && vehicleRequestDetected) {
  caseType = 'vehicle_based_search';
  intent = 'vehicle_search';
}
const invented = normalizedCodes.find(code => !textUpper.includes(code.toLocaleUpperCase('tr-TR')));
if (invented) {
  entities.productCodes = codes.filter(c => String(c?.code || c?.raw || c || '').trim() !== invented);
  action = 'handoff'; pauseAutomation = true; notifyAdmins = true;
  handoffReason = 'Mesajda bulunmayan ürün kodu engellendi';
  reply = 'Parça kodunuzu doğrulamak üzere talebinizi ürün uzmanımıza aktarıyorum.';
}

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

if (caseType === 'vehicle_based_search' || caseType === 'exact_code_compatibility') {
  notifyAdmins = true;
  if (!vehicleComplete && action !== 'handoff') {
    askVehicleInfo = true;
    reply = `Doğru filtreyi belirleyebilmemiz için lütfen şu bilgileri paylaşın: ${missingVehicleFields.join(', ')}. Alternatif olarak şasi numarasını iletebilirsiniz.`;
  } else if (action !== 'handoff') {
    reply = 'Araç bilgileriniz tamamlandı. Uygun filtre kodu, güncel stok ve net fiyat kontrol edilerek paylaşılacaktır.';
  }
} else if (caseType === 'exact_code_price_stock') {
  notifyAdmins = true;
  reply = `Filtre kodu ${normalizedCodes.join(', ')} için güncel stok ve net fiyat kontrol edilerek paylaşılacaktır.`;
} else if (caseType === 'cross_reference') {
  notifyAdmins = true;
  reply ||= 'Muadil parça talebiniz alındı. Üretici kataloğundan doğrulanarak stok ve fiyat bilgisi paylaşılacaktır.';
} else if (caseType === 'partial_code') {
  reply ||= 'Filtre kodunun tamamını veya aracınızın marka, model, yıl ve motor bilgisini paylaşabilir misiniz?';
} else if (caseType === 'greeting') {
  reply ||= 'Merhaba! Size nasıl yardımcı olabilirim?';
} else if (caseType === 'non_product' || intent === 'return_complaint') {
  action = 'handoff'; pauseAutomation = true; notifyAdmins = true;
  handoffReason ||= 'Şikayet, iade veya temsilci talebi';
  reply ||= 'Talebinizi ilgili ekibimize aktarıyorum. Yetkilimiz sizinle ilgilenecektir.';
}

const unsafeClaim = /\b\d+(?:[.,]\d+)?\s*(?:tl|₺)\b|\bstokta\b|kesin\s+uyar|bugün\s+kargo/i.test(reply);
if (unsafeClaim) {
  reply = 'Talebiniz alındı. Güncel stok, net fiyat ve uyumluluk bilgisi kontrol edilerek paylaşılacaktır.';
  notifyAdmins = true;
}
if (!reply) reply = 'Talebiniz alındı. Yetkilimiz kontrol ederek size bilgi verecektir.';
const escapedName = String(ctx.senderName || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
if (escapedName) reply = reply.replace(new RegExp(`^(Merhaba|Selam)\\s+${escapedName}\\s*(?:bey|hanım)?[,!:.]*\\s*`, 'i'), '$1, ');
reply = reply.replace(/\s+/g, ' ').trim();

const codeText = normalizedCodes.length ? normalizedCodes.map(code => `• ${code}`).join('\n') : 'Belirtilmedi';
const vehicleText = vehicleStrings.length ? vehicleStrings.map(vehicle => `• ${vehicle}`).join('\n') : (extractedVehicle ? `• ${extractedVehicle}` : 'Belirtilmedi');
let title = '📢 MÜŞTERİ TALEBİ / BİLDİRİM';
let requestedLines = ['✓ Stok', '✓ Net fiyat', '✓ Bugün kargo'];
if (caseType === 'vehicle_based_search') {
  title = '🚗 ARAÇ BAZLI PARÇA ARAMA';
  requestedLines = ['✓ Doğru parça tespiti', '✓ Araç uyumluluğu', '✓ Stok ve net fiyat', '✓ Bugün kargo'];
} else if (caseType === 'exact_code_compatibility') {
  title = '🛠️ UYUMLULUK VE PARÇA KONTROLÜ';
  requestedLines = ['✓ Araç/parça uyumluluğu', '✓ Stok ve net fiyat'];
} else if (caseType === 'cross_reference') {
  title = '🔄 MUADİL / ÇAPRAZ REFERANS TALEBİ';
  requestedLines = ['✓ Üretici kataloğu doğrulaması', '✓ Muadil kod', '✓ Stok ve net fiyat'];
} else if (caseType === 'exact_code_price_stock') {
  title = '🔥 SATIŞ GÖREVİ';
  requestedLines = ['✓ Stok', '✓ Net fiyat', '✓ Uyumluluk', '✓ Bugün kargo'];
} else if (caseType === 'non_product') {
  title = '⚠️ MÜŞTERİ DESTEK GÖREVİ';
  requestedLines = ['✓ Sipariş bilgisini kontrol et', '✓ Sorunu/yanlış ürünü doğrula', '✓ İade/değişim sürecini başlat', '✓ Müşteriyle iletişime geç'];
} else if (handoffReason.includes('ürün kodu')) {
  title = '🔎 ÜRÜN UZMANI İNCELEMESİ';
} else if (action === 'handoff') {
  title = '⚠️ AI DOĞRULAMA GEREKLİ';
}
const adminMessage = `${title}\n⏱️ SLA: 5 dk\n\n👤 ${ctx.senderName}\n📞 ${ctx.senderNumber}\n\n📦 Ürün/Kod\n${codeText}\n\n🚗 Araç\n${vehicleText}\n\n🎯 İstenen\n${requestedLines.join('\n')}\n\n👨 Atanan\n${ctx.assigneeName || 'İsmail Özkaracan'}\n\n──────────────\n\n💬 Müşteri\n"${originalText}"\n\n🤖 AI müşteriye gönderdi\n"${reply}"${handoffReason ? `\n\n📌 Handoff Nedeni: ${handoffReason}` : ''}`;
return { json: {
  ...ctx, intent, caseType, entities, cevap: reply, bildirim: adminMessage,
  notifyAdmins, replyCustomer: action !== 'ignore' && Boolean(reply), pauseAutomation,
  askVehicleInfo, expectsReply: askVehicleInfo || parsed.expectsReply === true,
  action, handoffReason, retryAi,
  parseFailureCode: retryAi ? 'invalid_ai_json' : null,
  parseFailureMessage: retryAi ? 'AI output could not be parsed as valid JSON' : null,
  fingerprint: `${caseType}:${normalizedCodes.sort().join(',')}:${vehicleStrings.join(',')}`
} };
""".strip()


prepare_catalog_js = r"""
const policy = $json || {};
const vehicles = Array.isArray(policy.entities?.vehicles) ? policy.entities.vehicles : [];
const vehicle = vehicles.find(v => v && typeof v === 'object') || {};
const text = String(policy.allMessagesText || '');
const intMatch = (pattern) => {
  const match = text.match(pattern);
  return match ? Number(match[1].replace(',', '.')) : null;
};
const vin = (text.toUpperCase().match(/\b[A-HJ-NPR-Z0-9]{17}\b/) || [])[0] || null;
const engineText = String(vehicle.engine || vehicle.motor || '').trim()
  || ((text.match(/\b\d[.,]\d\s*(?:TDI|TSI|DCI|HDI|MPI|CDTI|CRDI|BENZIN|DIZEL)?\b/i) || [])[0] || '');
return { json: {
  policy,
  senderNumber: policy.senderNumber,
  brand: String(vehicle.brand || '').trim() || null,
  model: String(vehicle.model || vehicle.modelSeries || '').trim() || null,
  engine: engineText || null,
  engineCode: String(vehicle.engineCode || '').trim() || null,
  powerKw: Number(vehicle.powerKw || vehicle.kw) || intMatch(/\b(\d{2,3})\s*kW\b/i),
  powerBhp: Number(vehicle.powerBhp || vehicle.bhp) || intMatch(/\b(\d{2,3})\s*(?:BHP|HP|BG|beygir)\b/i),
  displacement: Number(vehicle.displacementCcm || vehicle.ccm) || intMatch(/\b(\d{3,4})\s*(?:cc|ccm)\b/i),
  year: Number(vehicle.year) || intMatch(/\b(19\d{2}|20\d{2})\b/),
  fuelType: String(vehicle.fuelType || '').trim() || null,
  vin
} };
""".strip()


apply_catalog_js = r"""
const policy = typeof $json.policy === 'string' ? JSON.parse($json.policy) : ($json.policy || {});
const catalog = typeof $json.catalog === 'string' ? JSON.parse($json.catalog) : ($json.catalog || {});
const requiredLabels = { marka: 'marka', model: 'model serisi', motor: 'motor' };
const missing = (catalog.missingRequired || []).map(x => requiredLabels[x] || x);
const optional = (catalog.optionalFields || []).map(value => {
  const raw = String(value);
  if (/ccm/i.test(raw)) return 'hacim (ccm)';
  if (/kw|bhp/i.test(raw)) return 'g\u00fc\u00e7 (kW veya BHP)';
  if (/motor/i.test(raw)) return 'motor kodu';
  return '\u00fcretim y\u0131l\u0131';
});
let reply = String(policy.cevap || '');
let notifyAdmins = Boolean(policy.notifyAdmins);
let pauseAutomation = Boolean(policy.pauseAutomation);
let expectsReply = Boolean(policy.expectsReply);
if (catalog.status === 'missing_required') {
  reply = `Do\u011fru filtreyi belirleyebilmemiz i\u00e7in l\u00fctfen ${missing.join(', ')} bilgisini payla\u015f\u0131n. Varsa \u015fasi numaras\u0131n\u0131 da iletebilirsiniz.`;
  notifyAdmins = false; pauseAutomation = false; expectsReply = true;
} else if (catalog.status === 'ambiguous') {
  reply = `Ara\u00e7 bilgilerini netle\u015ftirmek i\u00e7in l\u00fctfen ${optional.join(', ')} bilgisini payla\u015f\u0131n. Varsa \u015fasi numaras\u0131n\u0131 da iletebilirsiniz.`;
  notifyAdmins = false; pauseAutomation = false; expectsReply = true;
} else if (catalog.status === 'unique') {
  reply = 'Ara\u00e7 bilgileriniz katalogda do\u011fruland\u0131. Uygun par\u00e7a, g\u00fcncel stok ve net fiyat kontrol edilerek payla\u015f\u0131lacakt\u0131r.';
  notifyAdmins = true; pauseAutomation = false;
} else if (catalog.status === 'no_match' && optional.length) {
  reply = `Katalog e\u015fle\u015fmesini netle\u015ftirmek i\u00e7in l\u00fctfen ${optional.join(', ')} bilgisini payla\u015f\u0131n. Varsa \u015fasi numaras\u0131n\u0131 da iletebilirsiniz.`;
  notifyAdmins = false; pauseAutomation = false; expectsReply = true;
} else if (catalog.status === 'no_match') {
  reply = 'Ara\u00e7 bilgileri katalogda kesin e\u015fle\u015fmedi. \u00dcr\u00fcn uzman\u0131m\u0131z uygun par\u00e7ay\u0131 kontrol ederek bilgi verecektir.';
  notifyAdmins = true;
}
const vehicle = catalog.vehicle || {};
const adminCatalog = `\n\nKatalog Kontrol\nDurum: ${catalog.status || 'bilinmiyor'}\nAday: ${Number(catalog.candidateCount || 0)}\nAra\u00e7: ${[vehicle.brand, vehicle.model, vehicle.engine].filter(Boolean).join(' / ') || 'Belirtilmedi'}${vehicle.vin ? `\n\u015easi: ${vehicle.vin}` : ''}`;
return { json: {
  ...policy, cevap: reply, notifyAdmins, pauseAutomation, expectsReply,
  bildirim: String(policy.bildirim || '') + adminCatalog,
  fingerprint: `${policy.fingerprint || 'vehicle'}:catalog:${catalog.status || 'unknown'}`,
  catalog
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
  errorMessage: String(ctx.parseFailureMessage || ctx.error?.message || ctx.message || 'AI execution failed').slice(0, 2000)
} };
""".strip()


prepare_delivery_js = r"""
const row = $json || {};
const payload = typeof row.payload === 'string' ? JSON.parse(row.payload) : (row.payload || {});
return { json: {
  deliveryId: String(row.id || ''), batchToken: String(row.batch_token || ''),
  channel: String(row.channel || ''), senderNumber: String(row.sender_number || ''),
  destination: String(row.destination || payload.number || ''), text: String(payload.text || ''),
  body: { number: String(row.destination || payload.number || ''), text: String(payload.text || '') }
} };
""".strip()


tag_success_js = r"""
const ctx = $('Prepare Delivery').item.json;
const providerId = String($json?.key?.id || $json?.messageId || $json?.id || '');
return { json: { ...ctx, success: true, providerId, errorMessage: '' } };
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
    if_node("Webhook Auth", "={{ $json.action !== 'unauthorized' }}", [1220, 240]),
    {
        "parameters": {"respondWith": "json", "responseBody": "={{ { accepted: false, error: 'unauthorized' } }}", "options": {"responseCode": 401}},
        "id": node_id("Respond Unauthorized"), "name": "Respond Unauthorized", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4, "position": [560, 440],
    },
    code_node("Normalize Payload", normalize_js, [340, 260]),
    if_node("Valid Event?", "={{ $json.valid === true }}", [560, 260]),
    {
        "parameters": {"respondWith": "json", "responseBody": "={{ { accepted: true, ignored: true } }}", "options": {"responseCode": 202}},
        "id": node_id("Respond Ignored"), "name": "Respond Ignored", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4, "position": [1000, 420],
    },
    postgres_node(
        "Ingest Message",
        "SELECT * FROM whatsapp_ai.ingest_message($1,$2,$3,$4::jsonb,$5,$6)",
        "={{ [ $json.messageId, $json.senderNumber, $json.senderName, JSON.stringify($json.message), $json.command, $json.queryToken ] }}",
        [780, 240],
    ),
    {
        "parameters": {"respondWith": "json", "responseBody": "={{ { accepted: true, action: $json.action || 'queued' } }}", "options": {"responseCode": 202}},
        "id": node_id("Respond Accepted"), "name": "Respond Accepted", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4, "position": [1220, 240],
    },
    {
        "parameters": {"rule": {"interval": [{"field": "seconds", "secondsInterval": 15}]}},
        "id": node_id("Schedule Trigger"), "name": "Schedule Trigger", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [120, 720],
    },
    postgres_node("OpenAI Circuit Gate", "SELECT whatsapp_ai.circuit_allows('openai') AS allowed", "={{ [] }}", [340, 620]),
    if_node("OpenAI Circuit Open?", "={{ $json.allowed === true }}", [560, 620]),
    postgres_node("Claim Ready Batches", "SELECT * FROM whatsapp_ai.claim_ready_batches(10)", "={{ [] }}", [780, 620]),
    code_node("Store Context", store_context_js, [1000, 620]),
    {
        "parameters": {"promptType": "define", "text": "={{ $json._prompt }}", "options": {"systemMessage": system_prompt}},
        "id": node_id("AI Agent"), "name": "AI Agent", "type": "@n8n/n8n-nodes-langchain.agent", "typeVersion": 3.1,
        "position": [1220, 620], "onError": "continueErrorOutput",
    },
    {
        "parameters": {"model": {"__rl": True, "value": "gpt-4o-mini", "mode": "list", "cachedResultName": "gpt-4o-mini"}, "builtInTools": {}, "options": {"temperature": 0.1, "maxTokens": 700}},
        "id": node_id("OpenAI Chat Model1"), "name": "OpenAI Chat Model1", "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi", "typeVersion": 1.3,
        "position": [1140, 840], "credentials": {"openAiApi": {"id": OPENAI_ID, "name": OPENAI_NAME}},
    },
    code_node("Parse AI Output", parse_ai_js, [1440, 560]),
    if_node("AI Output Valid?", "={{ $json.retryAi !== true }}", [1660, 560]),
    if_node("Vehicle Catalog?", "={{ $json.caseType === 'vehicle_based_search' }}", [1880, 520]),
    code_node("Prepare Catalog Lookup", prepare_catalog_js, [2100, 440]),
    postgres_node(
        "Resolve Vehicle Catalog",
        "SELECT $1::jsonb AS policy, whatsapp_ai.resolve_vehicle_context($2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) AS catalog",
        "={{ [ JSON.stringify($json.policy), $json.senderNumber, $json.brand, $json.model, $json.engine, $json.engineCode, $json.powerKw, $json.powerBhp, $json.displacement, $json.fuelType, $json.year, $json.vin ] }}",
        [2320, 440],
    ),
    code_node("Apply Catalog Decision", apply_catalog_js, [2540, 440]),
    postgres_node(
        "Complete AI Batch",
        "SELECT whatsapp_ai.complete_ai_batch($1,$2::uuid,$3,$4,$5,$6,$7,$8,$9) AS completed, whatsapp_ai.record_service_result('openai',true,NULL) AS circuit_state",
        "={{ [ $json.senderNumber, $json.batchToken, $json.cevap, $json.bildirim, $json.notifyAdmins, $json.replyCustomer, $json.pauseAutomation, $json.fingerprint, $json.caseType ] }}",
        [2760, 520],
    ),
    code_node("Prepare AI Failure", prepare_ai_failure_js, [1880, 700]),
    postgres_node(
        "Record AI Failure",
        "SELECT whatsapp_ai.record_ai_failure($1,$2::uuid,$3,$4) AS result, whatsapp_ai.record_service_result('openai',false,$3) AS circuit_state",
        "={{ [ $json.senderNumber, $json.batchToken, $json.errorCode, $json.errorMessage ] }}",
        [2100, 700],
    ),
    postgres_node("Evolution Circuit Gate", "SELECT whatsapp_ai.circuit_allows('evolution') AS allowed", "={{ [] }}", [340, 820]),
    if_node("Evolution Circuit Open?", "={{ $json.allowed === true }}", [560, 820]),
    postgres_node("Claim Deliveries", "SELECT * FROM whatsapp_ai.claim_deliveries(20)", "={{ [] }}", [780, 820]),
    code_node("Prepare Delivery", prepare_delivery_js, [560, 820]),
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "authentication": "predefinedCredentialType", "nodeCredentialType": "httpHeaderAuth",
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify($json.body) }}", "options": {"timeout": 15000},
        },
        "id": node_id("Send Delivery"), "name": "Send Delivery", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [780, 820], "onError": "continueErrorOutput",
        "credentials": {"httpHeaderAuth": {"id": EVOLUTION_ID, "name": EVOLUTION_NAME}},
    },
    code_node("Tag Delivery Success", tag_success_js, [1000, 800]),
    code_node("Tag Delivery Error", tag_error_js, [1000, 920]),
    postgres_node(
        "Record Delivery Result",
        "SELECT whatsapp_ai.record_delivery_result($1::uuid,$2,$3,$4) AS result, whatsapp_ai.record_service_result('evolution',$2,CASE WHEN $2 THEN NULL ELSE 'delivery_error' END) AS circuit_state",
        "={{ [ $json.deliveryId, $json.success, $json.providerId || null, $json.errorMessage || null ] }}",
        [1220, 840],
    ),
]


connections = {
    "Webhook1": {"main": [[edge("Normalize Payload")]]},
    "Normalize Payload": {"main": [[edge("Valid Event?")]]},
    "Valid Event?": {"main": [[edge("Ingest Message")], [edge("Respond Ignored")]]},
    "Ingest Message": {"main": [[edge("Webhook Auth")]]},
    "Webhook Auth": {"main": [[edge("Respond Accepted")], [edge("Respond Unauthorized")]]},
    "Schedule Trigger": {"main": [[edge("OpenAI Circuit Gate"), edge("Evolution Circuit Gate")]]},
    "OpenAI Circuit Gate": {"main": [[edge("OpenAI Circuit Open?")]]},
    "OpenAI Circuit Open?": {"main": [[edge("Claim Ready Batches")], []]},
    "Claim Ready Batches": {"main": [[edge("Store Context")]]},
    "Store Context": {"main": [[edge("AI Agent")]]},
    "AI Agent": {"main": [[edge("Parse AI Output")], [edge("Prepare AI Failure")]]},
    "Parse AI Output": {"main": [[edge("AI Output Valid?")]]},
    "AI Output Valid?": {"main": [[edge("Vehicle Catalog?")], [edge("Prepare AI Failure")]]},
    "Vehicle Catalog?": {"main": [[edge("Prepare Catalog Lookup")], [edge("Complete AI Batch")]]},
    "Prepare Catalog Lookup": {"main": [[edge("Resolve Vehicle Catalog")]]},
    "Resolve Vehicle Catalog": {"main": [[edge("Apply Catalog Decision")]]},
    "Apply Catalog Decision": {"main": [[edge("Complete AI Batch")]]},
    "Prepare AI Failure": {"main": [[edge("Record AI Failure")]]},
    "OpenAI Chat Model1": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
    "Evolution Circuit Gate": {"main": [[edge("Evolution Circuit Open?")]]},
    "Evolution Circuit Open?": {"main": [[edge("Claim Deliveries")], []]},
    "Claim Deliveries": {"main": [[edge("Prepare Delivery")]]},
    "Prepare Delivery": {"main": [[edge("Send Delivery")]]},
    "Send Delivery": {"main": [[edge("Tag Delivery Success")], [edge("Tag Delivery Error")]]},
    "Tag Delivery Success": {"main": [[edge("Record Delivery Result")]]},
    "Tag Delivery Error": {"main": [[edge("Record Delivery Result")]]},
}


workflow = {
    "name": "WhatsApp AI - v13 PostgreSQL Outbox",
    "nodes": nodes,
    "connections": connections,
    "settings": {
        "executionOrder": "v1", "timezone": "Europe/Istanbul",
        "saveDataErrorExecution": "all", "saveDataSuccessExecution": "none",
        "saveExecutionProgress": False, "executionTimeout": 600,
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
