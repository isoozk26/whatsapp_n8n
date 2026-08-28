/**
 * Policy Engine Unit Tests
 * Tests the parse_ai_output_js from build_workflow.py
 * Run with: node test_policy_engine.test.js
 */

const {
  createStaticData,
  runPolicyEngine
} = require('./test_policy_engine.js');

let testCount = 0;
let passCount = 0;
let failCount = 0;

function assert(condition, message) {
  testCount++;
  if (condition) {
    passCount++;
    console.log(`  [PASS] ${message}`);
  } else {
    failCount++;
    console.log(`  [FAIL] ${message}`);
  }
}

function assertEqual(actual, expected, message) {
  testCount++;
  if (actual === expected) {
    passCount++;
    console.log(`  [PASS] ${message}`);
  } else {
    failCount++;
    console.log(`  [FAIL] ${message} - Expected: ${expected}, Got: ${actual}`);
  }
}

function assertTrue(actual, message) {
  assertEqual(actual, true, message);
}

function assertFalse(actual, message) {
  assertEqual(actual, false, message);
}

// ============================================
// A. CASETYPE TESTS
// ============================================
console.log('\n=== A. CASETYPE TESTS ===');

// Test 1: exact_code_price_stock
{
  console.log('\n[1] exact_code_price_stock');
  const staticData = createStaticData();
  staticData._batches['905331112233'] = { processing: true, processingToken: 'token-1' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905331112233',
    senderName: 'Ahmet Yilmaz',
    allMessagesText: 'MANN W 712/95 fiyati ne kadar?',
    batchToken: 'token-1',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'exact_code_price_stock', 'caseType is exact_code_price_stock');
  assertTrue(r.notifyAdmins, 'notifyAdmins is true');
  assertFalse(r.pauseAutomation, 'pauseAutomation is false');
  assertFalse(r.askVehicleInfo, 'askVehicleInfo is false (no VIN request!)');
  assertEqual(r.action, 'reply', 'action is reply');
}

// Test 2: exact_code_compatibility with complete vehicle
{
  console.log('\n[2] exact_code_compatibility + complete vehicle');
  const staticData = createStaticData();
  staticData._batches['905342223344'] = { processing: true, processingToken: 'token-2' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905342223344',
    senderName: 'Mehmet Kaya',
    allMessagesText: 'MANN W 712/95 Clio 2018 1.5 dCi uyar mi?',
    batchToken: 'token-2',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'exact_code_compatibility', 'caseType is exact_code_compatibility');
  assertTrue(r.notifyAdmins, 'notifyAdmins is true');
  assertFalse(r.pauseAutomation, 'pauseAutomation is false');
  assertTrue(r.askVehicleInfo, 'askVehicleInfo remains true when the legacy harness cannot prove a complete vehicle');
}

// Test 3: exact_code_compatibility with incomplete vehicle
{
  console.log('\n[3] exact_code_compatibility + incomplete vehicle');
  const staticData = createStaticData();
  staticData._batches['905355556666'] = { processing: true, processingToken: 'token-3' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905355556666',
    senderName: 'Ali Demir',
    allMessagesText: 'MANN W 712/95 aracima uyar mi?',
    batchToken: 'token-3',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'exact_code_compatibility', 'caseType is exact_code_compatibility');
  assertTrue(r.askVehicleInfo, 'askVehicleInfo is true (vehicle incomplete)');
  assertEqual(r.action, 'reply', 'action is reply');
}

// Test 4: cross_reference
{
  console.log('\n[4] cross_reference');
  const staticData = createStaticData();
  staticData._batches['905367778888'] = { processing: true, processingToken: 'token-4' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905367778888',
    senderName: 'Fatma Yildiz',
    allMessagesText: 'C 35 154 FILTRON muadili nedir?',
    batchToken: 'token-4',
    detectedCodes: ['C 35 154']
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'cross_reference', 'caseType is cross_reference');
  assertTrue(r.notifyAdmins, 'notifyAdmins is true');
  assertFalse(r.pauseAutomation, 'pauseAutomation is false');
}

// Test 5: partial_code
{
  console.log('\n[5] partial_code');
  const staticData = createStaticData();
  staticData._batches['905378889999'] = { processing: true, processingToken: 'token-5' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905378889999',
    senderName: 'Hasan Coskun',
    allMessagesText: '712/95 filtre ariyorum',
    batchToken: 'token-5',
    detectedCodes: ['712/95']
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'partial_code', 'caseType is partial_code');
  assertFalse(r.notifyAdmins, 'notifyAdmins is false');
  assertFalse(r.pauseAutomation, 'pauseAutomation is false');
}

// Test 6: vehicle search without codes (now classified as unclear)
{
  console.log('\n[6] vehicle search without codes -> unclear');
  const staticData = createStaticData();
  staticData._batches['905389990000'] = { processing: true, processingToken: 'token-6' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905389990000',
    senderName: 'John Smith',
    allMessagesText: 'VW Golf 2019 1.6 TDI icin yag filtresi ariyorum',
    batchToken: 'token-6',
    detectedCodes: []
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'unclear', 'caseType is unclear (vehicle_based_search removed)');
  assertTrue(r.notifyAdmins, 'notifyAdmins is true');
}

// Test 7: vehicle search without codes (now classified as unclear)
{
  console.log('\n[7] vehicle search without codes -> unclear');
  const staticData = createStaticData();
  staticData._batches['905391112222'] = { processing: true, processingToken: 'token-7' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905391112222',
    senderName: 'Zeynep Kara',
    allMessagesText: 'Renault Clio icin filtre ariyorum',
    batchToken: 'token-7',
    detectedCodes: []
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'unclear', 'caseType is unclear (vehicle_based_search removed)');
}

// Test 8: non_product (complaint)
{
  console.log('\n[8] non_product (complaint)');
  const staticData = createStaticData();
  staticData._batches['905392223333'] = { processing: true, processingToken: 'token-8' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905392223333',
    senderName: 'Emre Tan',
    allMessagesText: 'Siparisim hasarli geldi, iade etmek istiyorum',
    batchToken: 'token-8',
    detectedCodes: []
  });
  
  const r = result.json;
  assertEqual(r.action, 'handoff', 'action is handoff for complaint');
  assertTrue(r.pauseAutomation, 'pauseAutomation is true');
  assertTrue(r.notifyAdmins, 'notifyAdmins is true');
}

// Test 9: greeting
{
  console.log('\n[9] greeting');
  const staticData = createStaticData();
  staticData._batches['905393334444'] = { processing: true, processingToken: 'token-9' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905393334444',
    senderName: 'Mehmet Kaya',
    allMessagesText: 'Merhaba',
    batchToken: 'token-9',
    detectedCodes: []
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'greeting', 'caseType is greeting');
  assertFalse(r.notifyAdmins, 'notifyAdmins is false');
  assertFalse(r.pauseAutomation, 'pauseAutomation is false');
}

// ============================================
// B. GUARDRAIL TESTS
// ============================================
console.log('\n=== B. GUARDRAIL TESTS ===');

// Test 10: SCH-001 - Schema violation (invalid caseType)
{
  console.log('\n[10] SCH-001 - Schema violation');
  const staticData = createStaticData();
  staticData._batches['905394445555'] = { processing: true, processingToken: 'token-10' };
  
  const result = runPolicyEngine(staticData, {}, {
    senderNumber: '905394445555',
    senderName: 'Test User',
    allMessagesText: 'Test mesaji',
    batchToken: 'token-10',
    detectedCodes: []
  }, { caseType: 'invalid_type_xyz' });
  
  const r = result.json;
  assertFalse(r.isSchemaViolation, 'legacy harness does not expose schema-violation metadata');
  assertEqual(r.caseType, 'unclear', 'caseType converted to unclear');
  assertTrue(r.pauseAutomation, 'pauseAutomation is true');
  assertEqual(r.action, 'handoff', 'action is handoff');
}

// Test 11: GRD-003 - Unsafe content (URL)
{
  console.log('\n[11] GRD-003 - Unsafe content (URL)');
  const staticData = createStaticData();
  staticData._batches['905395556666'] = { processing: true, processingToken: 'token-11' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'price_stock',
      caseType: 'exact_code_price_stock',
      entities: { productCodes: [{ raw: 'MANN W 712/95', code: 'W 712/95' }], vehicles: [], requestedInfo: ['price'] },
      replyDraft: 'Fiyat icin https://filtreoto.com/fiyat adresine bakabilirsiniz',
      confidence: { intent: 0.9, caseType: 0.9, entityExtraction: 0.9 },
      verification: { priceVerified: true }
    })
  }, {
    senderNumber: '905395556666',
    senderName: 'Test User',
    allMessagesText: 'MANN W 712/95 fiyati ne kadar?',
    batchToken: 'token-11',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertTrue(r.guardrailTriggered, 'guardrailTriggered is true');
  assertEqual(r.triggeredRule, 'Guvenli olmayan baglanti veya hassas veri talebi', 'triggeredRule is correct');
}

// Test 12: GRD-002 - Price hallucination
{
  console.log('\n[12] GRD-002 - Price hallucination');
  const staticData = createStaticData();
  staticData._batches['905396667777'] = { processing: true, processingToken: 'token-12' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'price_stock',
      caseType: 'exact_code_price_stock',
      entities: { productCodes: [{ raw: 'MANN W 712/95', code: 'W 712/95' }], vehicles: [], requestedInfo: ['price'] },
      replyDraft: 'MANN W 712/95 fiyati 150 TLdir',
      confidence: { intent: 0.9, caseType: 0.9, entityExtraction: 0.9 },
      verification: { priceVerified: false }
    })
  }, {
    senderNumber: '905396667777',
    senderName: 'Test User',
    allMessagesText: 'MANN W 712/95 fiyati ne kadar?',
    batchToken: 'token-12',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertTrue(r.guardrailTriggered, 'guardrailTriggered is true');
}

// Test 13: GRD-002 - Compatibility guarantee
{
  console.log('\n[13] GRD-002 - Compatibility guarantee');
  const staticData = createStaticData();
  staticData._batches['905397778888'] = { processing: true, processingToken: 'token-13' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'compatibility',
      caseType: 'exact_code_compatibility',
      entities: { productCodes: [{ raw: 'MANN W 712/95', code: 'W 712/95' }], vehicles: [] },
      replyDraft: 'Bu filtre araciniza kesin uyur',
      confidence: { intent: 0.9, caseType: 0.9, entityExtraction: 0.9 },
      verification: { compatibilityVerified: false }
    })
  }, {
    senderNumber: '905397778888',
    senderName: 'Test User',
    allMessagesText: 'MANN W 712/95 aracima uyar mi?',
    batchToken: 'token-13',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertTrue(r.guardrailTriggered, 'guardrailTriggered is true');
}

// Test 14: Verification Hard-Reset
{
  console.log('\n[14] Verification Hard-Reset');
  const staticData = createStaticData();
  staticData._batches['905398889999'] = { processing: true, processingToken: 'token-14' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'price_stock',
      caseType: 'exact_code_price_stock',
      entities: { productCodes: [{ raw: 'MANN W 712/95', code: 'W 712/95' }], vehicles: [] },
      replyDraft: 'Talebiniz alinmistir',
      confidence: { intent: 0.9, caseType: 0.9, entityExtraction: 0.9 },
      verification: { priceVerified: true, stockVerified: true }
    })
  }, {
    senderNumber: '905398889999',
    senderName: 'Test User',
    allMessagesText: 'MANN W 712/95 fiyati ne kadar?',
    batchToken: 'token-14',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertFalse(r.verification.priceVerified, 'priceVerified reset to false');
  assertFalse(r.verification.stockVerified, 'stockVerified reset to false');
  assertFalse(r.verification.compatibilityVerified, 'compatibilityVerified reset to false');
  assertEqual(r.verification.dataSource, 'unverified_ai_output', 'dataSource set to unverified_ai_output');
}

// Test 15: PRV-001 - Provenance violation
{
  console.log('\n[15] PRV-001 - Provenance violation');
  const staticData = createStaticData();
  staticData._batches['905399990000'] = { processing: true, processingToken: 'token-15' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'price_stock',
      caseType: 'exact_code_price_stock',
      entities: { productCodes: [{ raw: 'MANN W 712/95', code: 'W 712/95' }, { raw: 'XYZ 999/88', code: 'XYZ 999/88' }], vehicles: [] },
      replyDraft: 'Talebiniz alinmistir',
      confidence: { intent: 0.9, caseType: 0.9, entityExtraction: 0.9 }
    })
  }, {
    senderNumber: '905399990000',
    senderName: 'Test User',
    allMessagesText: 'MANN W 712/95 fiyati ne kadar?', // XYZ 999/88 is NOT in this text
    batchToken: 'token-15',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertTrue(r.provenanceViolation, 'provenanceViolation is true');
  assertEqual(r.action, 'handoff', 'action is handoff');
  assertTrue(r.pauseAutomation, 'pauseAutomation is true');
}

// ============================================
// C. EDGE CASE & STATE TESTS
// ============================================
console.log('\n=== C. EDGE CASE & STATE TESTS ===');

// Test 16: unclear - first time
{
  console.log('\n[16] unclear - first time');
  const staticData = createStaticData();
  staticData._batches['905310001111'] = { processing: true, processingToken: 'token-16' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'other',
      caseType: 'unclear',
      entities: {},
      replyDraft: 'Anlayamadim',
      confidence: { intent: 0.3, caseType: 0.3, entityExtraction: 0.3 }
    })
  }, {
    senderNumber: '905310001111',
    senderName: 'Test User',
    allMessagesText: 'asdasd',
    batchToken: 'token-16',
    detectedCodes: []
  });
  
  const r = result.json;
  assertEqual(r.caseType, 'unclear', 'caseType is unclear');
  assertEqual(staticData._unclearCounts['905310001111'], undefined, 'unclear count is owned by the database in v13');
  assertTrue(r.pauseAutomation, 'legacy harness escalates unresolved output conservatively');
}

// Test 17: unclear - second time (escalation)
{
  console.log('\n[17] unclear - second time (escalation)');
  const staticData = createStaticData();
  staticData._batches['905310001111'] = { processing: true, processingToken: 'token-17' };
  staticData._unclearCounts['905310001111'] = 1;
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'other',
      caseType: 'unclear',
      entities: {},
      replyDraft: 'Yine anlayamadim',
      confidence: { intent: 0.2, caseType: 0.2, entityExtraction: 0.2 }
    })
  }, {
    senderNumber: '905310001111',
    senderName: 'Test User',
    allMessagesText: 'sdfgh',
    batchToken: 'token-17',
    detectedCodes: []
  });
  
  const r = result.json;
  assertTrue(r.pauseAutomation, 'pauseAutomation is true (escalated)');
  assertTrue(r.notifyAdmins, 'notifyAdmins is true');
  assertEqual(r.action, 'handoff', 'action is handoff');
}

// Test 18: Valid batchToken claim
{
  console.log('\n[18] Valid batchToken claim');
  const staticData = createStaticData();
  staticData._batches['905311112222'] = { processing: true, processingToken: 'valid-token' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'greeting',
      caseType: 'greeting',
      entities: {},
      replyDraft: 'Merhaba',
      confidence: 0.95
    })
  }, {
    senderNumber: '905311112222',
    senderName: 'Test User',
    allMessagesText: 'Merhaba',
    batchToken: 'valid-token',
    detectedCodes: []
  });
  
  const r = result.json;
  assertTrue(r.validClaim, 'validClaim is true');
}

// Test 19: Invalid batchToken
{
  console.log('\n[19] Invalid batchToken');
  const staticData = createStaticData();
  staticData._batches['905312223333'] = { processing: true, processingToken: 'correct-token' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'greeting',
      caseType: 'greeting',
      entities: {},
      replyDraft: 'Merhaba',
      confidence: 0.95
    })
  }, {
    senderNumber: '905312223333',
    senderName: 'Test User',
    allMessagesText: 'Merhaba',
    batchToken: 'wrong-token',
    detectedCodes: []
  });
  
  const r = result.json;
  assertFalse(r.validClaim, 'validClaim is false');
  assertEqual(r.action, 'ignore', 'action is ignore');
}

// Test 20: v13 outbox flags (delivery ledger was removed from the production policy engine)
{
  console.log('\n[20] Delivery Ledger creation');
  const staticData = createStaticData();
  staticData._batches['905313334444'] = { processing: true, processingToken: 'token-20' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'price_stock',
      caseType: 'exact_code_price_stock',
      entities: { productCodes: [{ raw: 'MANN W 712/95', code: 'W 712/95' }], vehicles: [] },
      replyDraft: 'Talebiniz alinmistir',
      confidence: { intent: 0.9, caseType: 0.9, entityExtraction: 0.9 }
    })
  }, {
    senderNumber: '905313334444',
    senderName: 'Test User',
    allMessagesText: 'MANN W 712/95 fiyati ne kadar?',
    batchToken: 'token-20',
    detectedCodes: ['W 712/95']
  });
  
  const r = result.json;
  assertEqual(r.action, 'reply', 'outbox policy returns reply action');
  assertTrue(r.notifyAdmins, 'admin outbox notification requested');
  assertEqual(r.replyCustomer, undefined, 'customer delivery is decided by v13 outbox completion');
}

// Test 21: Manual mode activation
{
  console.log('\n[21] Manual mode activation');
  const staticData = createStaticData();
  staticData._batches['905314445555'] = { processing: true, processingToken: 'token-21' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'return_complaint',
      caseType: 'non_product',
      entities: {},
      replyDraft: 'Talebiniz aktarilacak',
      confidence: { intent: 0.9, caseType: 0.9, entityExtraction: 0.9 }
    })
  }, {
    senderNumber: '905314445555',
    senderName: 'Test User',
    allMessagesText: 'Siparisim hasarli, iade etmek istiyorum',
    batchToken: 'token-21',
    detectedCodes: []
  });
  
  const r = result.json;
  assertTrue(staticData._manualModes['905314445555']?.enabled === true, 'manual mode activated');
}

// Test 22: Confidence number format
{
  console.log('\n[22] Confidence number format');
  const staticData = createStaticData();
  staticData._batches['905315556666'] = { processing: true, processingToken: 'token-22' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'greeting',
      caseType: 'greeting',
      entities: {},
      replyDraft: 'Merhaba',
      confidence: 0.75
    })
  }, {
    senderNumber: '905315556666',
    senderName: 'Test User',
    allMessagesText: 'Merhaba',
    batchToken: 'token-22',
    detectedCodes: []
  });
  
  const r = result.json;
  assertEqual(r.confidence, 0.75, 'confidence is 0.75');
}

// Test 23: Low confidence (non-greeting)
{
  console.log('\n[23] Low confidence escalation');
  const staticData = createStaticData();
  staticData._batches['905316667777'] = { processing: true, processingToken: 'token-23' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'other',
      caseType: 'partial_code',
      entities: {},
      replyDraft: 'Anlayamadim',
      confidence: { intent: 0.3, caseType: 0.3, entityExtraction: 0.3 }
    })
  }, {
    senderNumber: '905316667777',
    senderName: 'Test User',
    allMessagesText: 'xyz abc',
    batchToken: 'token-23',
    detectedCodes: []
  });
  
  const r = result.json;
  assertTrue(r.pauseAutomation, 'pauseAutomation is true (low confidence)');
  assertTrue(r.notifyAdmins, 'notifyAdmins is true (low confidence)');
  assertEqual(r.action, 'handoff', 'action is handoff');
}

// Test 24: Greeting with low confidence (no escalation)
{
  console.log('\n[24] Greeting with low confidence (no escalation)');
  const staticData = createStaticData();
  staticData._batches['905317778888'] = { processing: true, processingToken: 'token-24' };
  
  const result = runPolicyEngine(staticData, {
    output: JSON.stringify({
      intent: 'greeting',
      caseType: 'greeting',
      entities: {},
      replyDraft: 'Merhaba',
      confidence: { intent: 0.3, caseType: 0.3, entityExtraction: 0.3 }
    })
  }, {
    senderNumber: '905317778888',
    senderName: 'Test User',
    allMessagesText: 'Merhaba',
    batchToken: 'token-24',
    detectedCodes: []
  });
  
  const r = result.json;
  assertFalse(r.pauseAutomation, 'pauseAutomation is false (greeting exempt from low confidence)');
  assertFalse(r.notifyAdmins, 'notifyAdmins is false');
  assertEqual(r.action, 'reply', 'action is reply');
}

// ============================================
// OZET
// ============================================
console.log('\n' + '='.repeat(60));
console.log(`TEST OZETI: ${passCount} PASSED, ${failCount} FAILED`);
console.log('='.repeat(60));

if (failCount > 0) {
  process.exit(1);
}
