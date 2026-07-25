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

function context(text = "MANN W 712/95 fiyati nedir?") {
  return { senderNumber: "905320000001", senderName: "Mann Filtre", batchToken: "00000000-0000-0000-0000-000000000001", allMessagesText: text };
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
  assert.strictEqual(result.json.schemaVersion, "13.5");
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
    replyDraft: "Merhaba Mann Filtre, MANN W 712/95 talebiniz alindi.",
  });
  assert(name.json.cevap.includes("kaç adet düşündüğünüzü"));
  assert(name.json.cevap.includes("mesai saatleri içinde") || name.json.cevap.includes("Mesai dışındayız"));
  assert(!name.json.cevap.startsWith("Merhaba Mann Filtre"));

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
  assert(directCode.json.cevap.includes("ürün uzmanımız"));

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
  assert(missingCode.json.cevap.includes("iki yoldan biri yeterli"));
  assert(missingCode.json.bildirim.includes("ek bilgi bekleniyor"));
  assert(!missingCode.json.bildirim.includes("STOK/FIYAT SORGUSU"));
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
  await testPolicy();
  await testDeliveryTags();
  await testBatchCompletionFailure();
  await testAiFailurePreparation();
  console.log("[PASS] normalize, policy, guardrail and delivery behaviors");
})().catch((error) => { console.error("[FAIL]", error.stack || error); process.exit(1); });
