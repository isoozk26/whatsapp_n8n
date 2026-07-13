#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const assert = require("assert");

const root = path.resolve(__dirname, "..");
const workflow = JSON.parse(fs.readFileSync(path.join(root, "workflow.json"), "utf8"));
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

function codeOf(name) {
  const node = workflow.nodes.find((item) => item.name === name);
  assert(node, `Node bulunamadı: ${name}`);
  return node.parameters.jsCode;
}

async function execute(code, staticData, input, lookup = () => ({ item: { json: {} } })) {
  const fn = new AsyncFunction("$getWorkflowStaticData", "$input", "$", "$item", code);
  return fn(() => staticData, input, lookup, lookup);
}

function webhookInput(number, text, fromMe, id) {
  return {
    first: () => ({
      json: {
        body: {
          data: {
            key: { remoteJid: `${number}@s.whatsapp.net`, fromMe, id },
            pushName: "Davranış Testi",
            message: { conversation: text },
          },
        },
      },
    }),
  };
}

function context(token = "batch-1", text = "MANN W 712/95 fiyatı nedir?") {
  return {
    senderNumber: "905320000001",
    senderName: "Test Müşteri",
    allMessagesText: text,
    messageCount: 1,
    batchToken: token,
    detectedCodes: text.includes("W 712/95") ? ["W 712/95"] : [],
  };
}

function stateFor(ctx) {
  return {
    _batches: {
      [ctx.senderNumber]: {
        pendingMessages: [],
        processingMessages: [{ text: ctx.allMessagesText }],
        processing: true,
        processingToken: ctx.batchToken,
        processingStartedAt: Date.now(),
      },
    },
    _manualModes: {},
  };
}

async function runParse(aiOutput, ctx = context(), state = stateFor(ctx)) {
  const input = { item: { json: { output: aiOutput } } };
  const lookup = (name) => {
    assert.strictEqual(name, "Store Context");
    return { item: { json: ctx } };
  };
  const result = await execute(codeOf("Parse AI Output"), state, input, lookup);
  return { result: result.json, state };
}

function baseAi(overrides = {}) {
  return {
    intent: "price_stock",
    caseType: "exact_code_price_stock",
    entities: {
      productCodes: [{ raw: "MANN W 712/95", code: "W 712/95", brand: "MANN-FILTER" }],
      vehicles: [],
      requestedInfo: ["price", "stock"],
      preferredBrands: [],
      quantity: "Belirtilmedi",
    },
    missingFields: [],
    replyDraft: "Stok ve fiyat yetkilimiz tarafından kontrol edilecektir.",
    confidence: { intent: 0.95, caseType: 0.95, entityExtraction: 0.95 },
    verification: {
      catalogVerified: false,
      stockVerified: false,
      priceVerified: false,
      compatibilityVerified: false,
    },
    ...overrides,
  };
}

async function testCommandsAndCleanup() {
  const state = { _batches: {}, _manualModes: {}, _seenMessageIds: {} };
  const collector = codeOf("Batch Collector");
  const plus = await execute(collector, state, webhookInput("905320000001", "++", true, "cmd-plus"));
  assert.strictEqual(plus[0].json.command, "paused");
  assert.strictEqual(state._manualModes["905320000001"], true);

  const minus = await execute(collector, state, webhookInput("905320000001", "--", true, "cmd-minus"));
  assert.strictEqual(minus[0].json.command, "resumed");
  assert.strictEqual(Object.hasOwn(state._manualModes, "905320000001"), false);
  assert.strictEqual(typeof state._lastSeenCleanupAt, "number");
}

async function testTimeoutRecoveryAndIdle() {
  const number = "905320000002";
  const now = Date.now();
  const state = {
    _manualModes: { legacyFalse: false },
    _batches: {
      [number]: {
        pendingMessages: [{ text: "yeni", time: "10:01" }],
        processingMessages: [{ text: "eski", time: "10:00" }],
        pendingStartedAt: now - 121000,
        lastMessageAt: now - 121000,
        processing: true,
        processingStartedAt: now - 121000,
        processingToken: "expired",
      },
    },
  };
  const ready = await execute(codeOf("Stale Batch Check"), state, {}, () => ({}));
  assert.strictEqual(ready[0].json.messageCount, 2);
  assert.strictEqual(state._batches[number].processing, true);
  assert.notStrictEqual(state._batches[number].processingToken, "expired");
  assert.strictEqual(Object.hasOwn(state._manualModes, "legacyFalse"), false);

  const idleState = { _lastReply: { [number]: now - 11 * 60 * 1000 } };
  const alerts = await execute(codeOf("Idle Timeout Check"), idleState, {}, () => ({}));
  assert.strictEqual(alerts[0].json._idleAlert, true);
  assert.strictEqual(Object.hasOwn(idleState._lastReply, number), false);
}

async function testPolicyAndGuardrails() {
  const normal = await runParse(baseAi());
  assert.strictEqual(normal.result.action, "reply");
  assert.strictEqual(normal.result.notifyAdmins, true);
  assert.deepStrictEqual(normal.state._deliveryLedger["batch-1"].expected, {
    phoneA: true,
    phoneB: true,
    customer: true,
  });

  const price = await runParse(baseAi({ replyDraft: "Ürün stokta var, fiyatı 350 TL." }));
  assert(!price.result.cevap.includes("350"));
  assert(!price.result.cevap.toLocaleLowerCase("tr-TR").includes("stokta var"));

  const invented = baseAi({
    entities: {
      productCodes: [{ raw: "MANN W 9999", code: "W 9999" }],
      vehicles: [],
      requestedInfo: ["price"],
      preferredBrands: [],
      quantity: "Belirtilmedi",
    },
  });
  const provenance = await runParse(invented, context("batch-1", "Golf hava filtresi arıyorum"));
  assert.strictEqual(provenance.result.action, "handoff");
  assert.strictEqual(provenance.result.pauseAutomation, true);

  const lowConfidence = await runParse(baseAi({
    confidence: { intent: 0.4, caseType: 0.4, entityExtraction: 0.4 },
  }));
  assert.strictEqual(lowConfidence.result.action, "handoff");

  const schema = await runParse(baseAi({ caseType: "invented_case_type" }));
  assert.strictEqual(schema.result.action, "handoff");
  assert(schema.result.handoffReason.includes("İhlali") || schema.result.handoffReason.includes("hlali"));

  const vehicle = await runParse(baseAi({
    intent: "vehicle_search",
    caseType: "vehicle_based_search",
    entities: { productCodes: [], vehicles: ["Volkswagen Golf"], requestedInfo: [], preferredBrands: [], quantity: "Belirtilmedi" },
  }), context("batch-1", "Golf için hava filtresi"));
  assert.strictEqual(vehicle.result.askVehicleInfo, true);
  assert.strictEqual(vehicle.result.expectsReply, true);

  const unclearState = stateFor(context());
  const unclearAi = baseAi({ intent: "unclear", caseType: "unclear", entities: { productCodes: [], vehicles: [] } });
  const first = await runParse(unclearAi, context(), unclearState);
  assert.strictEqual(first.result.action, "reply");
  const second = await runParse(unclearAi, context(), unclearState);
  assert.strictEqual(second.result.action, "handoff");
  assert.strictEqual(second.result.pauseAutomation, true);

  const wrongContext = context("wrong-token");
  const invalid = await runParse(baseAi(), wrongContext, stateFor(context("real-token")));
  assert.strictEqual(invalid.result.action, "ignore");
  assert.strictEqual(invalid.result.validClaim, false);
}

async function testDeliveryLedgerPermutations() {
  const permutations = [
    ["phoneA", "phoneB", "customer"],
    ["phoneA", "customer", "phoneB"],
    ["phoneB", "phoneA", "customer"],
    ["phoneB", "customer", "phoneA"],
    ["customer", "phoneA", "phoneB"],
    ["customer", "phoneB", "phoneA"],
  ];
  const finalize = codeOf("Finalize Batch");
  for (const order of permutations) {
    const ctx = context("delivery-token");
    const parsed = { ...ctx, action: "reply", pauseAutomation: false, expectsReply: false };
    const state = stateFor(ctx);
    state._deliveryLedger = {
      [ctx.batchToken]: {
        createdAt: Date.now(),
        expected: { phoneA: true, phoneB: true, customer: true },
        completed: {},
      },
    };
    for (let index = 0; index < order.length; index += 1) {
      const channel = order[index];
      await execute(
        finalize,
        state,
        { item: { json: { completedChannel: channel } } },
        (name) => {
          assert.strictEqual(name, "Parse AI Output");
          return { $json: parsed };
        },
      );
      if (index < order.length - 1) assert(state._deliveryLedger[ctx.batchToken]);
    }
    assert.strictEqual(Object.hasOwn(state._deliveryLedger, ctx.batchToken), false);
    assert.strictEqual(Object.hasOwn(state._batches, ctx.senderNumber), false);
    assert.strictEqual(typeof state._finalizedTokens[ctx.batchToken], "number");
  }
}

async function testNonBatchNotificationBypass() {
  const finalize = codeOf("Finalize Batch");
  const commandState = {};
  const command = await execute(
    finalize,
    commandState,
    { item: { json: { delivered: true } } },
    (name) => {
      if (name === "Batch Collector") {
        return { $json: { _action: "command", command: "paused", senderNumber: "905320000001" } };
      }
      throw new Error(`${name} bu execution yolunda yok`);
    },
  );
  assert.strictEqual(command.json.command, "paused");
  assert.strictEqual(commandState._finalizedTokens, undefined);

  const idleState = {};
  const idle = await execute(
    finalize,
    idleState,
    { item: { json: { delivered: true } } },
    (name) => {
      if (name === "Idle Timeout Check") {
        return { $json: { _idleAlert: true, senderNumber: "905320000002" } };
      }
      throw new Error(`${name} bu execution yolunda yok`);
    },
  );
  assert.strictEqual(idle.json._idleAlert, true);
  assert.strictEqual(idleState._finalizedTokens, undefined);
}

async function main() {
  await testCommandsAndCleanup();
  await testTimeoutRecoveryAndIdle();
  await testPolicyAndGuardrails();
  await testDeliveryLedgerPermutations();
  await testNonBatchNotificationBypass();
  console.log("[PASS] policy, guardrail, timeout, manual-mode, idle and delivery-ledger behaviors");
}

main().catch((error) => {
  console.error("[FAIL]", error.stack || error);
  process.exit(1);
});
