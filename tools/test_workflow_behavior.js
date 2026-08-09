#!/usr/bin/env node
"use strict";
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const workflow = JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "workflow.json"), "utf8"));
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

function codeOf(name) {
  const found = workflow.nodes.find((item) => item.name === name);
  assert(found, `node missing: ${name}`);
  return found.parameters.jsCode;
}

const staticDataStore = {};
const $input = { first: () => ({ json }), item: { json: {} } };
const runtimeThis = { getWorkflowStaticData: (scope) => staticDataStore };

async function execute(code, json, lookup = () => ({ item: { json: {} } }), env = {}) {
  const fn = new AsyncFunction("$json", "$", "$env", "$getWorkflowStaticData", "$input", code);
  return fn.call(runtimeThis, json, lookup, env, runtimeThis.getWorkflowStaticData, $input);
}

function webhook(data, nested = false) {
  return {
    query: { token: "test" },
    body: nested ? { body: { data } } : { data },
  };
}

function headerWebhook(data) {
  return {
    headers: { "x-webhook-secret": "header-token" },
    query: {},
    body: { data },
  };
}

async function testNormalize() {
  const data = {
    key: { remoteJid: "905320000001@s.whatsapp.net", fromMe: false, id: "msg-1" },
    pushName: "Mann Filtre",
    message: { conversation: "MANN W 712/95 fiyati nedir?" },
  };
  const normal = await execute(codeOf("Normalize Payload"), webhook(data), () => ({}), { OWNER_PHONE_NUMBERS: "905000000000" });
  const rateLimited = await execute(codeOf("Normalize Payload"), webhook(data), () => ({}), { OWNER_PHONE_NUMBERS: "905000000000" });
  const nested = await execute(codeOf("Normalize Payload"), webhook(data, true), () => ({}), { OWNER_PHONE_NUMBERS: "905000000000" });
  const { timestamp: normalTimestamp, ...normalMessage } = normal.json.message;
  const { timestamp: nestedTimestamp, ...nestedMessage } = nested.json.message;
  assert.deepStrictEqual(normalMessage, nestedMessage);
  assert.strictEqual(typeof normalTimestamp, "number");
  assert.strictEqual(typeof nestedTimestamp, "number");
  assert.strictEqual(normal.json.valid, true);
  assert.strictEqual(normal.json.senderNumber, "905320000001");
  assert.strictEqual(normal.json.rateLimitExceeded, false);
  assert.strictEqual(rateLimited.json.rateLimitExceeded, true);
  const lid = structuredClone(data);
  lid.key.remoteJid = "11149818998846@lid";
  const lidNormalized = await execute(codeOf("Normalize Payload"), webhook(lid), () => ({}), {});
  assert.strictEqual(lidNormalized.json.valid, true);
  assert.strictEqual(lidNormalized.json.senderNumber, "11149818998846@lid");
  const header = await execute(codeOf("Normalize Payload"), headerWebhook(data), () => ({}), {});
  assert.strictEqual(header.json.webhookToken, "header-token");
  assert.strictEqual(header.json.authSource, "header");

  const group = structuredClone(data);
  group.key.remoteJid = "120000@g.us";
  assert.strictEqual((await execute(codeOf("Normalize Payload"), webhook(group), () => ({}), {})).json.valid, false);

  const command = structuredClone(data);
  command.key.fromMe = true;
  command.message.conversation = "++";
  assert.strictEqual((await execute(codeOf("Normalize Payload"), webhook(command), () => ({}), {})).json.command, "pause");
}

async function testAdminNumberFilter() {
  const data = {
    key: { remoteJid: "905360000001@s.whatsapp.net", fromMe: false, id: "admin-msg-1" },
    pushName: "Admin",
    message: { conversation: "Merhaba" },
  };
  const normalized = await execute(codeOf("Normalize Payload"), webhook(data), () => ({}), {});
  const filtered = await execute(codeOf("Apply Admin Number Filter"), {
    adminPhoneA: "905360000001",
    adminPhoneB: "222",
  }, (name) => {
    assert.strictEqual(name, "Normalize Payload");
    return { item: { json: normalized.json } };
  });
  assert.strictEqual(filtered.json.isAdminNumber, true);

  const normal = await execute(codeOf("Apply Admin Number Filter"), {
    adminPhoneA: "111",
    adminPhoneB: "222",
  }, () => ({ item: { json: { ...normalized.json, senderNumber: "905360999999" } } }));
  assert.strictEqual(normal.json.isAdminNumber, false);

  const normalCustomer = await execute(codeOf("Apply Admin Number Filter"), {
    adminPhoneA: "111",
    adminPhoneB: "222",
  }, () => ({ item: { json: { ...normalized.json, senderNumber: "905320000001" } } }));
  assert.strictEqual(normalCustomer.json.isAdminNumber, false);

  const exactAdminA = await execute(codeOf("Apply Admin Number Filter"), {
    adminPhoneA: "111",
    adminPhoneB: "222",
  }, () => ({ item: { json: { ...normalized.json, senderNumber: "111" } } }));
  assert.strictEqual(exactAdminA.json.isAdminNumber, true);

  const exactAdminB = await execute(codeOf("Apply Admin Number Filter"), {
    adminPhoneA: "111",
    adminPhoneB: "222",
  }, () => ({ item: { json: { ...normalized.json, senderNumber: "222" } } }));
  assert.strictEqual(exactAdminB.json.isAdminNumber, true);
}

function context(text = "MANN W 712/95 fiyati nedir?", chatMemoryText = "") {
  return { senderNumber: "905320000001", senderName: "Mann Filtre", batchToken: "00000000-0000-0000-0000-000000000001", allMessagesText: text, chatMemoryText };
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ı/g, "i")
    .replace(/İ/g, "i")
    .replace(/ğ/g, "g")
    .replace(/Ğ/g, "g")
    .replace(/ş/g, "s")
    .replace(/Ş/g, "s")
    .replace(/ç/g, "c")
    .replace(/Ç/g, "c")
    .replace(/ö/g, "o")
    .replace(/Ö/g, "o")
    .replace(/ü/g, "u")
    .replace(/Ü/g, "u");
}

async function runParse(ai, ctx = context()) {
  return execute(codeOf("Parse AI Output"), { output: JSON.stringify(ai) }, (name) => {
    assert.strictEqual(name, "Store Context");
    return { item: { json: ctx } };
  });
}

async function testPolicy() {
  const base = {
    intent: "price_stock", caseType: "exact_code_price_stock",
    entities: { productCodes: [{ code: "W 712/95" }], vehicles: [] },
    replyDraft: "Talebiniz alindi, kontrol edilecek.", confidence: 0.95,
  };
  const result = await runParse(base);
  assert.strictEqual(result.json.notifyAdmins, true);
  assert.strictEqual(result.json.replyCustomer, true);
  assert(result.json.bildirim.includes("Yan\u0131t Haz\u0131rland\u0131"));
  assert.strictEqual(result.json.schemaVersion, "13.6");
  assert.strictEqual(result.json.funnelStage, "F4 Dönüşüm");

  const unsafe = await runParse({
    intent: "other",
    caseType: "other",
    entities: {},
    replyDraft: "Stokta var, fiyati 350 TL.",
    confidence: 0.95,
  }, context("Bana şu parça için fiyat verin"));
  assert(!unsafe.json.cevap.includes("350"));
  assert(!unsafe.json.cevap.toLowerCase().includes("stokta var"));
  assert(unsafe.json.cevap.includes("Talebinizi ürün uzmanımıza ilettik"));

  const unsafeTurkish = await runParse({
    intent: "other",
    caseType: "other",
    entities: {},
    replyDraft: "Bugün kargo ile orijinal parça gönderiyoruz.",
    confidence: 0.95,
  }, context("Bana şu parça için bilgi verin"));
  assert(!unsafeTurkish.json.cevap.toLowerCase().includes("kargo"));
  assert(!unsafeTurkish.json.cevap.toLowerCase().includes("orijinal"));

  const invented = await runParse({ ...base, entities: { productCodes: [{ code: "XYZ 999" }] } });
  assert.strictEqual(invented.json.action, "handoff");
  assert.strictEqual(invented.json.pauseAutomation, true);

  const complaint = await runParse({ ...base, intent: "return_complaint", caseType: "non_product", entities: {}, replyDraft: "Aktariyorum" }, context("Yanlis urun geldi, iade istiyorum"));
  assert(complaint.json.bildirim.includes("\u0130ADE/DE\u011e\u0130\u015e\u0130M TALEB\u0130"));
  assert.strictEqual(complaint.json.pauseAutomation, true);
  assert.strictEqual(complaint.json.notifyAdmins, true);
  assert(!complaint.json.bildirim.includes("Bugun kargo"));
  assert.strictEqual(complaint.json.cevap.includes("✅"), false);
  assert(["📦", "🛠️", "🔄", "🔎", "👋", "🤝", "📝", "📌"].every((prefix) => !complaint.json.cevap.startsWith(prefix)), true);

  const name = await runParse({
    ...base,
    intent: "other",
    caseType: "partial_code",
    entities: { productCodes: [{ code: "WX123" }], vehicles: [] },
    replyDraft: "Merhaba Mann Filtre, MANN W 712/95 talebiniz alindi.",
  });
  assert(name.json.cevap.includes("fotoğrafını gönderebilir misiniz"));
  assert.strictEqual((name.json.cevap.match(/\?/g) || []).length, 1);
  assert(name.json.cevap.includes("mesai saatleri içinde") || name.json.cevap.includes("Mesai dışındayız"));
  assert(!name.json.cevap.startsWith("Merhaba Mann Filtre"));

  const missingAll = await runParse({
    ...base,
    intent: "other",
    caseType: "partial_code",
    entities: { productCodes: [], vehicles: [] },
    replyDraft: "",
    confidence: 0.2,
  }, context("Filtre kodu yok"));
  assert(missingAll.json.cevap.includes("onu yazar mısınız"));
  assert.strictEqual((missingAll.json.cevap.match(/\?/g) || []).length, 1);

  const quantitySingle = await runParse({
    ...base,
    entities: { productCodes: [{ code: "BOSCH F026400287" }], vehicles: [] },
    replyDraft: "Talebiniz alindi, kontrol edilecek.",
  }, context("BOSCH F026400287 5 adet lazım"));
  assert.strictEqual(quantitySingle.json.entities.quantity, 5);
  assert.strictEqual(quantitySingle.json.isBulkOrder, false);

  const quantityBulk = await runParse({
    ...base,
    entities: { productCodes: [{ code: "MN134" }], vehicles: [] },
    replyDraft: "Talebiniz alindi, kontrol edilecek.",
  }, context("MN134 20 tane lazım"));
  assert.strictEqual(quantityBulk.json.entities.quantity, 20);
  assert.strictEqual(quantityBulk.json.isBulkOrder, true);
  assert(quantityBulk.json.bildirim.includes("Toplu sipariş"));

  const commercialLead = await runParse({
    intent: "greeting",
    caseType: "greeting",
    entities: { productCodes: [], vehicles: [] },
    replyDraft: "Merhaba, Filtre Oto'ya hoş geldiniz. Filtre kodunu ya da aracınızın şasi numarasını yazmanız yeterli — uygun ürünü birlikte netleştirelim. Hangi araç için bakıyorsunuz?",
    confidence: 0.92,
  }, context("16 Kalem Filtre alımı için fiyat almak istiyoruz"));
  assert.strictEqual(commercialLead.json.entities.quantity, 16);
  assert.strictEqual(commercialLead.json.isBulkOrder, true);
  assert.strictEqual(commercialLead.json.caseType, "partial_code");
  assert.strictEqual(commercialLead.json.partialSubType, "bulk_request");
  assert.strictEqual(commercialLead.json.intent, "price_stock");
  assert.strictEqual(commercialLead.json.replyCustomer, true);
  assert.strictEqual(commercialLead.json.pauseAutomation, false);
  assert.strictEqual(commercialLead.json.reason, "bulk_purchase_intent");
  assert.deepStrictEqual(commercialLead.json.missingFields, []);
  assert.strictEqual(commercialLead.json.notifyAdmins, true);
  assert(commercialLead.json.bildirim.includes("TOPLU ALIM TALEBİ"));

  const smallCommercialLead = await runParse({
    intent: "greeting",
    caseType: "greeting",
    entities: { productCodes: [], vehicles: [] },
    replyDraft: "Merhaba, Filtre Oto'ya hoş geldiniz. Filtre kodunu ya da aracınızın şasi numarasını yazmanız yeterli — uygun ürünü birlikte netleştirelim. Hangi araç için bakıyorsunuz?",
    confidence: 0.92,
  }, context("3 kalem filtre alacağız fiyat verir misiniz"));
  assert.strictEqual(smallCommercialLead.json.entities.quantity, 3);
  assert.strictEqual(smallCommercialLead.json.isBulkOrder, false);
  assert.strictEqual(smallCommercialLead.json.caseType, "partial_code");
  assert.strictEqual(smallCommercialLead.json.partialSubType, "bulk_request");
  assert.strictEqual(smallCommercialLead.json.notifyAdmins, true);
  assert.strictEqual(smallCommercialLead.json.pauseAutomation, false);
  assert.strictEqual(smallCommercialLead.json.reason, "bulk_purchase_intent");
  assert.deepStrictEqual(smallCommercialLead.json.missingFields, []);
  assert(smallCommercialLead.json.bildirim.includes("TOPLU ALIM TALEBİ"));

  const noisyB2B = await runParse({
    intent: "greeting",
    caseType: "greeting",
    entities: { productCodes: [], vehicles: [] },
    replyDraft: "Merhaba, Filtre Oto'ya hoş geldiniz. Filtre kodunu ya da aracınızın şasi numarasını yazmanız yeterli — uygun ürünü birlikte netleştirelim. Hangi araç için bakıyorsunuz?",
    confidence: 0.92,
  }, context("b2b"));
  assert.strictEqual(noisyB2B.json.caseType, "greeting");
  assert.strictEqual(noisyB2B.json.notifyAdmins, false);
  assert.strictEqual(noisyB2B.json.pauseAutomation, false);

  const toptanBayi = await runParse({
    intent: "greeting",
    caseType: "greeting",
    entities: { productCodes: [], vehicles: [] },
    replyDraft: "Merhaba, Filtre Oto'ya hoş geldiniz. Filtre kodunu ya da aracınızın şasi numarasını yazmanız yeterli — uygun ürünü birlikte netleştirelim. Hangi araç için bakıyorsunuz?",
    confidence: 0.92,
  }, context("Toptan filtre almak istiyoruz bayiyiz"));
  assert.strictEqual(toptanBayi.json.caseType, "partial_code");
  assert.strictEqual(toptanBayi.json.partialSubType, "bulk_request");
  assert.strictEqual(toptanBayi.json.notifyAdmins, true);
  assert.strictEqual(toptanBayi.json.pauseAutomation, false);
  assert.strictEqual(toptanBayi.json.reason, "bulk_purchase_intent");
  assert.deepStrictEqual(toptanBayi.json.missingFields, []);
  assert(toptanBayi.json.bildirim.includes("TOPLU ALIM TALEBİ"));

  const media = await runParse({
    intent: "other",
    caseType: "other",
    entities: {},
    replyDraft: "",
    confidence: 0.9,
  }, { ...context("[Medya]"), allMessagesText: "[Medya]", isMediaMessage: true, mediaType: "image" });
  assert(media.json.cevap.includes("mesajınızı aldık, ürün uzmanımız inceliyor"));
  assert(media.json.cevap.includes("tek cümleyle özetler misiniz"));

  const hasan = await runParse({
    intent: "vehicle_search",
    caseType: "unclear",
    entities: { productCodes: [], vehicles: [] },
    replyDraft: "Talebiniz alindi. Yetkilimiz kontrol ederek size bilgi verecektir.",
    confidence: 0.31,
  }, {
    ...context("1. [09:30] Merhaba Fiat Egea 2022 yag filtresi ariyorum"),
    senderName: "Hasandurgun",
    assigneeName: "Ismail Ozkaracan",
  });
  assert.strictEqual(hasan.json.caseType, "unclear");
  assert.strictEqual(hasan.json.action, "reply");
  assert.strictEqual(hasan.json.pauseAutomation, false);

  const invalid = await execute(codeOf("Parse AI Output"), { output: "not-json" }, () => ({ item: { json: context() } }));
  assert.strictEqual(invalid.json.action, "reply");
  assert.strictEqual(invalid.json.retryAi, true);
  assert.strictEqual(invalid.json.pauseAutomation, false);

  const hasanInvalid = await execute(codeOf("Parse AI Output"), { output: "not-json" }, () => ({ item: { json: {
    ...context("1. [21:09] Merhaba Fiat Egea 2022 yag filtresi ariyorum\n2. [21:09] Mann filtre marka var mi"),
    senderName: "Hasandurgun",
    assigneeName: "Ismail Ozkaracan",
  } } }));
  assert.strictEqual(hasanInvalid.json.caseType, "unclear");
  assert.strictEqual(hasanInvalid.json.action, "reply");
  assert.strictEqual(hasanInvalid.json.retryAi, false);
  assert.strictEqual(hasanInvalid.json.pauseAutomation, false);
  assert(hasanInvalid.json.bildirim.includes("Mann filtre marka var mi"));

  const vehicleDetails = await runParse({
    intent: "vehicle_search", caseType: "unclear",
    entities: { productCodes: [], vehicles: [] }, replyDraft: "", confidence: 0.2,
  }, context("1. [21:22] Fiat Egea 2022 yag filtresi\n2. [21:23] 1.6 TDI motor"));
  assert.strictEqual(vehicleDetails.json.pauseAutomation, false);

  const directCode = await runParse({
    intent: "other", caseType: "other", entities: {}, replyDraft: "", confidence: 0.2,
  }, { ...context("MANN W 712/95 filtre stok fiyat"), detectedCodes: ["W 712/95"] });
  assert.strictEqual(directCode.json.caseType, "exact_code_price_stock");
  assert.strictEqual(directCode.json.pauseAutomation, false);
  assert(directCode.json.cevap.includes("kaç adet düşündüğünüzü"));
  assert(directCode.json.cevap.includes("güncel stok"));

  const fingerprintA = await runParse({
    intent: "other",
    caseType: "other",
    entities: {},
    replyDraft: "",
    confidence: 0.2,
  }, { ...context("MANN W 712/95 filtre stok fiyat"), detectedCodes: ["W 712/95"], senderNumber: "905320000001" });
  const fingerprintB = await runParse({
    intent: "other",
    caseType: "other",
    entities: {},
    replyDraft: "",
    confidence: 0.2,
  }, { ...context("MANN W 712/95 filtre stok fiyat"), detectedCodes: ["W 712/95"], senderNumber: "905320000002" });
  assert(fingerprintA.json.fingerprint.startsWith("905320000001:"));
  assert(fingerprintB.json.fingerprint.startsWith("905320000002:"));
  assert.notStrictEqual(fingerprintA.json.fingerprint, fingerprintB.json.fingerprint);

  const noFalseCode = await runParse({
    intent: "price_stock", caseType: "exact_code_price_stock",
    entities: { productCodes: [{ code: "EGEA 2022 I" }, { code: "130 HP" }], vehicles: [] },
    replyDraft: "", confidence: 0.3,
  }, { ...context("1. [21:43] Fiat Egea 2022 icin yakit filtresi varmi\n2. [21:43] Mann filtre\n3. [21:44] 130 HP"), detectedCodes: [] });
  assert.strictEqual(noFalseCode.json.caseType, "partial_code");
  assert.strictEqual(noFalseCode.json.pauseAutomation, false);
  assert.strictEqual(noFalseCode.json.entities.productCodes.length, 0);

  const missingCode = await runParse({
    intent: "price_stock", caseType: "exact_code_price_stock",
    entities: { productCodes: [], vehicles: [] }, replyDraft: "", confidence: 0.95,
  }, { ...context("Mann c 35 050 filtre varmi"), detectedCodes: [] });
  assert.strictEqual(missingCode.json.caseType, "partial_code");
  assert(!missingCode.json.cevap.includes("guncel stok"));
  assert(missingCode.json.cevap.includes("şasi numarası"));
  assert(missingCode.json.bildirim.includes("ek bilgi bekleniyor"));
  assert(!missingCode.json.bildirim.includes("STOK/FIYAT SORGUSU"));

  const vinMemory = await runParse({
    intent: "compatibility", caseType: "exact_code_compatibility",
    entities: { productCodes: [], vehicles: [] }, replyDraft: "", confidence: 0.9,
  }, context("Polen filtresi", "Müşteri: WDB2100351A528399\nMüşteri: Mercedes E200 1998"));
  assert.strictEqual(vinMemory.json.action, "reply");
  assert(!normalizeText(vinMemory.json.cevap).toLowerCase().includes("sasi"));
  const vinDirect = await runParse({
    intent: "compatibility", caseType: "exact_code_compatibility",
    entities: { productCodes: [], vehicles: [] }, replyDraft: "", confidence: 0.9,
  }, context("Polen filtresi WDB2100351A528399"));
  assert(vinDirect.json.bildirim.includes("WDB2100351A528399"));
  assert(vinDirect.json.bildirim.includes(vinDirect.json.senderNumber));
  assert(!vinDirect.json.bildirim.includes("******"));
  assert(!vinDirect.json.bildirim.includes("***"));

  const marketplace = await runParse({ ...base, intent: "other", caseType: "other", replyDraft: "" }, context("N11'de var mı?"));
  assert(normalizeText(marketplace.json.cevap).toLowerCase().includes("pazaryerlerinde"));
  assert(marketplace.json.cevap.includes("filtreoto.com"));

  const shipping = await runParse({ ...base, intent: "other", caseType: "other", replyDraft: "" }, context("Bugün sipariş versem cumartesi gelir mi?"));
  assert(normalizeText(shipping.json.cevap).toLowerCase().includes("aras kargo"));
  assert(shipping.json.cevap.includes("2-3 iş günü"));
  assert(!normalizeText(shipping.json.cevap).toLowerCase().includes("garantili"));

  const authenticity = await runParse({ ...base, intent: "other", caseType: "other", replyDraft: "" }, context("Ürünler orijinal mi, fatura var mı?"));
  assert(normalizeText(authenticity.json.cevap).toLowerCase().includes("etbis"));
  assert(normalizeText(authenticity.json.cevap).toLowerCase().includes("3d secure"));
}

async function testOohMessages() {
  const baseCtx = {
    senderNumber: "905320000001",
    senderName: "Mann Filtre",
    scenario: "evening",
    istanbulDay: "Cumartesi",
    istanbulTime: "19:30",
    isHoliday: false,
    offHours: true,
    correlationId: "corr-1",
    nextAiAttemptAt: "2026-07-28T06:00:00.000Z",
  };
  const lookup = (name) => {
    if (name === "Check Business Hours") {
      return { item: { json: baseCtx } };
    }
    if (name === "Claim OOH Notification") {
      return { item: { json: {
        adminPhoneA: "905052237182",
        adminPhoneB: "905306056066",
        claimed: true,
        oohLogId: "00000000-0000-0000-0000-000000000002",
      } } };
    }
    throw new Error(`unexpected lookup: ${name}`);
  };

  const fresh = await execute(codeOf("Build OOH Messages"), {}, lookup);
  assert.strictEqual(fresh.json.sendCustomer, true);
  assert.strictEqual(fresh.json.customerSent, true);
  assert.strictEqual(fresh.json.managerSent, true);
  assert.deepStrictEqual(fresh.json.managerTargets, ["905052237182", "905306056066"]);
  assert.strictEqual(fresh.json.nextAiAttemptAt, "2026-07-28T06:00:00.000Z");
  assert(fresh.json.customerMsg.includes("Mesajınız için teşekkür ederiz."));
  assert(!fresh.json.customerMsg.includes("Mann Filtre"));
  assert(fresh.json.customerMsg.includes("09:00 itibarıyla"));
  assert(fresh.json.managerMsg.includes("Mesai Dışı Müşteri Bildirimi"));
  assert(fresh.json.managerMsg.includes("Mann Filtre"));
  assert(fresh.json.managerMsg.includes("gönderilecek."));

  const cooledLookup = (name) => {
    if (name === "Check Business Hours") {
      return { item: { json: { ...baseCtx, scenario: "holiday", istanbulDay: "Pazar", istanbulTime: "10:15", isHoliday: true } } };
    }
    if (name === "Claim OOH Notification") {
      return { item: { json: {
        adminPhoneA: "905052237182",
        adminPhoneB: "905306056066",
        claimed: false,
        oohLogId: null,
      } } };
    }
    throw new Error(`unexpected lookup: ${name}`);
  };

  const cooled = await execute(codeOf("Build OOH Messages"), {}, cooledLookup);
  assert.strictEqual(cooled.json.sendCustomer, false);
  assert.strictEqual(cooled.json.customerSent, false);
  assert(cooled.json.managerMsg.includes("cooldown nedeniyle atlandı"));
  assert(normalizeText(cooled.json.customerMsg).includes("resmi tatil"));
}

async function testBusinessHoursNextAttempt() {
  const result = await execute(codeOf("Check Business Hours"), {
    overrideNow: "2026-07-27T19:30:00+03:00",
    senderNumber: "905320000001",
    senderName: "Mann Filtre",
  });
  assert.strictEqual(result.json.offHours, true);
  assert.strictEqual(result.json.scenario, "evening");
  assert.strictEqual(result.json.nextAiAttemptAt, "2026-07-28T06:00:00.000Z");
  assert.deepStrictEqual(result.json.businessWindow, [9, 18]);
}

async function testDeliveryTags() {
  const ctx = { deliveryId: "d1", channel: "phone_b", body: { number: "1", text: "x" } };
  const lookup = (name) => { assert.strictEqual(name, "Prepare Delivery"); return { item: { json: ctx } }; };
  const ok = await execute(codeOf("Tag Delivery Success"), { key: { id: "provider-1" } }, lookup);
  const missing = await execute(codeOf("Tag Delivery Success"), {}, lookup);
  const err = await execute(codeOf("Tag Delivery Error"), { error: { message: "timeout" } }, lookup);
  assert.strictEqual(ok.json.success, true);
  assert.strictEqual(ok.json.providerId, "provider-1");
  assert.strictEqual(missing.json.success, false);
  assert.strictEqual(missing.json.errorMessage, "missing_provider_message_id");
  assert.strictEqual(err.json.success, false);
  assert.strictEqual(err.json.errorMessage, "timeout");
}

async function testBatchCompletionFailure() {
  const result = await execute(codeOf("Prepare Batch Completion Failure"), {
    senderNumber: "905320000001",
    batchToken: "00000000-0000-0000-0000-000000000001",
    completionFailureCode: "batch_completion_failed",
    completionFailureMessage: "complete_ai_batch returned false",
  });
  assert.strictEqual(result.json.senderNumber, "905320000001");
  assert.strictEqual(result.json.batchToken, "00000000-0000-0000-0000-000000000001");
  assert.strictEqual(result.json.parseFailureCode, "batch_completion_failed");
  assert.strictEqual(result.json.parseFailureMessage, "complete_ai_batch returned false");
}

async function testAiFailurePreparation() {
  const result = await execute(codeOf("Prepare AI Failure"), {
    senderNumber: "905320000001",
    batchToken: "00000000-0000-0000-0000-000000000001",
    parseFailureCode: "ai_schema_invalid",
    parseFailureMessage: "fixture failure",
  });
  assert.strictEqual(result.json.errorCode, "ai_schema_invalid");
  assert.strictEqual(result.json.errorMessage, "fixture failure");
  assert.strictEqual(result.json.senderNumber, "905320000001");
}

(async () => {
  await testNormalize();
  await testAdminNumberFilter();
  await testPolicy();
  await testBusinessHoursNextAttempt();
  await testOohMessages();
  await testDeliveryTags();
  await testBatchCompletionFailure();
  await testAiFailurePreparation();
  console.log("[PASS] normalize, policy, guardrail and delivery behaviors");
})().catch((error) => { console.error("[FAIL]", error.stack || error); process.exit(1); });
