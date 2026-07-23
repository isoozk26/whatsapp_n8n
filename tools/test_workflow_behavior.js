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

async function execute(code, json, lookup = () => ({ item: { json: {} } }), env = {}) {
  const fn = new AsyncFunction("$json", "$", "$env", code);
  return fn(json, lookup, env);
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
    message: { conversation: "MANN W 712/95 fiyatı nedir?" },
  };
  const normal = await execute(codeOf("Normalize Payload"), webhook(data), () => ({}), { OWNER_PHONE_NUMBERS: "905000000000" });
  const nested = await execute(codeOf("Normalize Payload"), webhook(data, true), () => ({}), { OWNER_PHONE_NUMBERS: "905000000000" });
  const { timestamp: normalTimestamp, ...normalMessage } = normal.json.message;
  const { timestamp: nestedTimestamp, ...nestedMessage } = nested.json.message;
  assert.deepStrictEqual(normalMessage, nestedMessage);
  assert.strictEqual(typeof normalTimestamp, "number");
  assert.strictEqual(typeof nestedTimestamp, "number");
  assert.strictEqual(normal.json.valid, true);
  assert.strictEqual(normal.json.senderNumber, "905320000001");
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

function context(text = "MANN W 712/95 fiyatı nedir?") {
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
    replyDraft: "Talebiniz alındı, kontrol edilecek.", confidence: 0.95,
  };
  const result = await runParse(base);
  assert.strictEqual(result.json.notifyAdmins, true);
  assert.strictEqual(result.json.replyCustomer, true);
  assert(result.json.bildirim.includes("Yanıt Gönderildi"));

  const unsafe = await runParse({ ...base, replyDraft: "Stokta var, fiyatı 350 TL." });
  assert(!unsafe.json.cevap.includes("350"));
  assert(!unsafe.json.cevap.toLowerCase().includes("stokta var"));

  const invented = await runParse({ ...base, entities: { productCodes: [{ code: "XYZ 999" }] } });
  assert.strictEqual(invented.json.action, "handoff");
  assert.strictEqual(invented.json.pauseAutomation, true);

  const complaint = await runParse({ ...base, intent: "return_complaint", caseType: "non_product", entities: {}, replyDraft: "Aktarıyorum" }, context("Yanlış ürün geldi, iade istiyorum"));
  assert(complaint.json.bildirim.includes("ŞİKAYET / İADE"));
  assert.strictEqual(complaint.json.pauseAutomation, true);
  assert.strictEqual(complaint.json.notifyAdmins, true);
  assert(!complaint.json.bildirim.includes("Bugün kargo"));

  const name = await runParse({
    ...base,
    intent: "other",
    caseType: "partial_code",
    replyDraft: "Merhaba Mann Filtre, MANN W 712/95 talebiniz alındı.",
  });
  assert(name.json.cevap.includes("W 712/95"));
  assert(!name.json.cevap.startsWith("Merhaba Mann Filtre"));

  const hasan = await runParse({
    intent: "vehicle_search",
    caseType: "unclear",
    entities: { productCodes: [], vehicles: [] },
    replyDraft: "Talebiniz alındı. Yetkilimiz kontrol ederek size bilgi verecektir.",
    confidence: 0.31,
  }, {
    ...context("1. [09:30] Merhaba Fiat Egea 2022 yağ filtresi arıyorum"),
    senderName: "Hasandurgun",
    assigneeName: "İsmail Özkaracan",
  });
  assert.strictEqual(hasan.json.caseType, "unclear");
  assert.strictEqual(hasan.json.action, "reply");
  assert.strictEqual(hasan.json.pauseAutomation, false);

  const invalid = await execute(codeOf("Parse AI Output"), { output: "not-json" }, () => ({ item: { json: context() } }));
  assert.strictEqual(invalid.json.action, "retry");
  assert.strictEqual(invalid.json.retryAi, true);
  assert.strictEqual(invalid.json.pauseAutomation, false);

  const hasanInvalid = await execute(codeOf("Parse AI Output"), { output: "not-json" }, () => ({ item: { json: {
    ...context("1. [21:09] Merhaba Fiat Egea 2022 yağ filtresi arıyorum\n2. [21:09] Mann filtre marka var mı"),
    senderName: "Hasandurgun",
    assigneeName: "İsmail Özkaracan",
  } } }));
  assert.strictEqual(hasanInvalid.json.caseType, "unclear");
  assert.strictEqual(hasanInvalid.json.action, "reply");
  assert.strictEqual(hasanInvalid.json.retryAi, false);
  assert.strictEqual(hasanInvalid.json.pauseAutomation, false);
  assert(hasanInvalid.json.bildirim.includes("Mann filtre marka var mı"));

  const vehicleDetails = await runParse({
    intent: "vehicle_search", caseType: "unclear",
    entities: { productCodes: [], vehicles: [] }, replyDraft: "", confidence: 0.2,
  }, context("1. [21:22] Fiat Egea 2022 yağ filtresi\n2. [21:23] 1.6 TDI motor"));
  assert.strictEqual(vehicleDetails.json.pauseAutomation, false);

  const directCode = await runParse({
    intent: "other", caseType: "other", entities: {}, replyDraft: "", confidence: 0.2,
  }, { ...context("MANN W 712/95 filtre stok fiyat"), detectedCodes: ["W 712/95"] });
  assert.strictEqual(directCode.json.caseType, "exact_code_price_stock");
  assert.strictEqual(directCode.json.pauseAutomation, false);
  assert(directCode.json.cevap.includes("W 712/95"));
  assert(directCode.json.cevap.includes("güncel stok ve net fiyat"));

  const noFalseCode = await runParse({
    intent: "price_stock", caseType: "exact_code_price_stock",
    entities: { productCodes: [{ code: "EGEA 2022 I" }, { code: "130 HP" }], vehicles: [] },
    replyDraft: "", confidence: 0.3,
  }, { ...context("1. [21:43] Fiat Egea 2022 için yakıt filtresi varmı\n2. [21:43] Mann filtre\n3. [21:44] 130 HP"), detectedCodes: [] });
  assert.strictEqual(noFalseCode.json.caseType, "partial_code");
  assert.strictEqual(noFalseCode.json.pauseAutomation, false);
  assert.strictEqual(noFalseCode.json.entities.productCodes.length, 0);

  const missingCode = await runParse({
    intent: "price_stock", caseType: "exact_code_price_stock",
    entities: { productCodes: [], vehicles: [] }, replyDraft: "", confidence: 0.95,
  }, { ...context("Mann c 35 050 filtre varmi"), detectedCodes: [] });
  assert.strictEqual(missingCode.json.caseType, "partial_code");
  assert(!missingCode.json.cevap.includes("güncel stok"));
  assert(missingCode.json.cevap.includes("kodunun tamamını"));
  assert(missingCode.json.bildirim.includes("EKSİK BİLGİ"));
  assert(!missingCode.json.bildirim.includes("STOK/FİYAT SORGUSU"));
}

async function testDeliveryTags() {
  const ctx = { deliveryId: "d1", channel: "phone_b", body: { number: "1", text: "x" } };
  const lookup = (name) => { assert.strictEqual(name, "Prepare Delivery"); return { item: { json: ctx } }; };
  const ok = await execute(codeOf("Tag Delivery Success"), { key: { id: "provider-1" } }, lookup);
  const err = await execute(codeOf("Tag Delivery Error"), { error: { message: "timeout" } }, lookup);
  assert.strictEqual(ok.json.success, true);
  assert.strictEqual(ok.json.providerId, "provider-1");
  assert.strictEqual(err.json.success, false);
  assert.strictEqual(err.json.errorMessage, "timeout");
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
  await testAiFailurePreparation();
  console.log("[PASS] normalize, policy, guardrail and delivery behaviors");
})().catch((error) => { console.error("[FAIL]", error.stack || error); process.exit(1); });
