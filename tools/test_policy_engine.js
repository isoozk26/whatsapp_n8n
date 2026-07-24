/**
 * Policy Engine Test Harness
 * Extracts parse_ai_output_js from build_workflow.py and wraps it with n8n mocks
 */

function createStaticData() {
  return {
    _batches: {},
    _manualModes: {},
    _seenMessageIds: {},
    _unclearCounts: {},
    _adminNotifications: {},
    _deliveryLedger: {},
    _finalizedTokens: {},
    _lastReply: {},
    _lastSeenCleanupAt: 0
  };
}

function mockGetWorkflowStaticData(staticData) {
  return function(scope) {
    if (scope !== 'global') throw new Error('Only global scope supported in tests');
    return staticData;
  };
}

function mockInput(inputJson) {
  return { item: { json: inputJson } };
}

function mockStoreContext(storeContextJson) {
  return { item: { json: storeContextJson } };
}

// The actual parse_ai_output_js extracted from build_workflow.py
// Using template literal for clean multi-line string
const parseAiOutputJs = `
const staticData = $getWorkflowStaticData('global');
const currentInput = $input.item.json;
const rawAiOutput = currentInput?.output || currentInput?.aiResult || '';
const aiOutput = typeof rawAiOutput === 'string' ? rawAiOutput : JSON.stringify(rawAiOutput);

let senderNumber = '';
let senderName = '';
let allMessagesText = '';
let batchToken = '';
let detectedCodes = [];
try {
  const sc = $('Store Context').item.json;
  senderNumber = String(sc.senderNumber || '');
  senderName = String(sc.senderName || senderNumber || 'Bilinmeyen musteri');
  allMessagesText = String(sc.allMessagesText || '');
  batchToken = String(sc.batchToken || '');
  if (Array.isArray(sc.detectedCodes)) detectedCodes = sc.detectedCodes;
} catch(e) {
  console.error('[Parse AI Output] Store Context okunamadi:', e?.message || e);
  throw new Error('Parse AI Output gerekli Store Context verisine ulasamadi');
}

if (!staticData._unclearCounts) staticData._unclearCounts = {};
if (!staticData._batches) staticData._batches = {};
if (!staticData._adminNotifications) staticData._adminNotifications = {};

const batch = staticData._batches[senderNumber];
const validClaim = Boolean(batch && batch.processing === true && batch.processingToken === batchToken);

if (!validClaim && senderNumber) {
  return { json: {
    senderNumber, senderName, batchToken, action: 'ignore', intent: 'other', caseType: 'other',
    cevap: '', missingFields: [], confidence: 0, handoffReason: 'Gecersiz veya suresi dolmus islem yutuldu',
    notifyAdmins: false, validClaim: false, bildirim: ''
  }};
}

let parsed = null;
if (typeof rawAiOutput === 'object' && rawAiOutput !== null) {
  parsed = rawAiOutput;
} else {
  try {
    const cleaned = aiOutput.replace(/^\`\\{3}(?:json)?\\s*/i, '').replace(/\\s*\`\\{3}$/i, '').trim();
    parsed = JSON.parse(cleaned);
  } catch (e1) {
    try {
      const match = aiOutput.match(/\\{[\\s\\S]*\\}/);
      if (match) parsed = JSON.parse(match[0]);
    } catch(e2) {
      console.error('[Parse AI Output] AI JSON ayristirilamadi:', e1?.message || e1, e2?.message || e2);
    }
  }
}

// If no AI output provided, determine caseType from detectedCodes and allMessagesText
if (!parsed && detectedCodes.length > 0) {
  const textLower = allMessagesText.toLowerCase();
  // Check for cross_reference keywords
  const hasCrossRefKeywords = /\\b(muadil|eşdeğer|eşdeger|karşılığı|karsiligi|çapraz|capraz|referans|nedir)\\b/i.test(allMessagesText);
  const hasVehicleInfo = /\\b(?:fiat|renault|ford|volkswagen|vw|opel|peugeot|citroen|toyota|honda|hyundai|kia|mercedes|bmw|audi|skoda|seat|dacia|nissan)\\b/i.test(allMessagesText);
  const hasYearInfo = /\\b(?:19\\d{2}|20\\d{2})\\b/.test(allMessagesText);
  const hasEngineInfo = /\\b\\d[.,]\\d\\s*(?:tdi|tsi|dci|hdi|cdti|bengin|dizel)?\\b/i.test(allMessagesText) || /\\b\\d+\\s*(?:hp|bg|kw|cc)\\b/i.test(allMessagesText);
  const hasCompatibilityKeywords = /\\b(uyma|uyar|uygun|uyumluluk|takilir|oturur|gecer|calisir)\\b/i.test(allMessagesText);
  const hasPartialCodeKeywords = /\\b(ariyorum|arıyorum|istiyorum|lazim|lazim)\\b/i.test(allMessagesText);
  const isShortCode = detectedCodes.some(c => c.replace(/[^a-zA-Z0-9]/g, '').length <= 4);

  if (hasCrossRefKeywords) {
    parsed = { intent: 'cross_reference', caseType: 'cross_reference', entities: { productCodes: detectedCodes.map(c => ({ code: c })), vehicles: [] }, confidence: 0.8 };
  } else if (hasCompatibilityKeywords || (hasVehicleInfo && !isShortCode)) {
    // Extract vehicle info from text
    const brands = ['Fiat','Renault','Ford','Volkswagen','VW','Opel','Peugeot','Citroen','Toyota','Honda','Hyundai','Kia','Mercedes','BMW','Audi','Skoda','Seat','Dacia','Nissan'];
    const detectedBrand = brands.find(b => new RegExp('\\\\b' + b + '\\\\b', 'i').test(allMessagesText));
    const yearMatch = allMessagesText.match(/\\b(19\\d{2}|20\\d{2})\\b/);
    const engineMatch = allMessagesText.match(/\\b(\\d[.,]\\d)\\s*(?:TDI|TSI|DCI|HDI|CDTI|MPI|CRDI|BENZIN|DIZEL)?\\b/i);
    const powerMatch = allMessagesText.match(/\\b(\\d{2,3})\\s*(?:hp|bg|kw|beygir)\\b/i);
    // Extract model - text between brand and year/engine
    let model = '';
    if (detectedBrand) {
      const afterBrand = allMessagesText.slice(allMessagesText.toLowerCase().indexOf(detectedBrand.toLowerCase()) + detectedBrand.length);
      const modelPart = afterBrand.split(/\\b(?:19\\d{2}|20\\d{2})\\b/)[0]
        .replace(/\\b(?:yağ|yag|hava|yakit|filtre|filtresi|ariyorum|için|icin|uyar|uyumluluk)\\b/gi, ' ')
        .replace(/[^\\p{L}\\p{N}.-]+/gu, ' ').trim().split(/\\s+/).slice(0, 3).join(' ');
      model = modelPart;
    }
    const vehicles = [{
      brand: detectedBrand || null,
      model: model || null,
      year: yearMatch?.[1] || null,
      engine: (engineMatch?.[1] || '') + (engineMatch?.[2] ? ' ' + engineMatch[2] : ''),
      power: powerMatch ? powerMatch[1] + ' hp' : null,
      raw: allMessagesText
    }];
    parsed = { intent: 'compatibility', caseType: 'exact_code_compatibility', entities: { productCodes: detectedCodes.map(c => ({ code: c })), vehicles }, confidence: 0.8 };
  } else if (hasPartialCodeKeywords || isShortCode) {
    parsed = { intent: 'other', caseType: 'partial_code', entities: { productCodes: detectedCodes.map(c => ({ code: c })), vehicles: [] }, confidence: 0.6 };
  } else {
    parsed = { intent: 'price_stock', caseType: 'exact_code_price_stock', entities: { productCodes: detectedCodes.map(c => ({ code: c })), vehicles: [] }, confidence: 0.8 };
  }
} else if (!parsed && allMessagesText) {
  const textLower = allMessagesText.toLowerCase();
  const greetingWords = ['merhaba', 'selam', 'gunaydin', 'iyi gunler', 'iyi aksamlar'];
  if (greetingWords.some(w => textLower.includes(w)) && textLower.length < 30) {
    parsed = { intent: 'greeting', caseType: 'greeting', entities: {}, confidence: 0.9 };
  } else {
    parsed = { intent: 'other', caseType: 'unclear', entities: {}, confidence: 0.3 };
  }
}

if (!parsed) {
  return { json: {
    senderNumber, senderName, batchToken, action: 'handoff', intent: 'unclear', caseType: 'unclear',
    cevap: 'Talebinizi ilgili ekibimize aktariyoruz. Yetkilimiz sizinle ilgilenecektir.',
    missingFields: [], confidence: 0, handoffReason: 'AI JSON ayristirma hatasi',
    notifyAdmins: true, validClaim: true, pauseAutomation: true,
    bildirim: 'AI CIKTISI AYRISTIRILAMADI musteri: ' + senderName + ' (' + senderNumber + ') mesaj: ' + allMessagesText
  }};
}

const intent = String(parsed.intent || 'other').trim();
let caseType = String(parsed.caseType || intent || 'other').trim();
const entities = parsed.entities || {};
let replyDraft = String(parsed.replyDraft || parsed.reply || parsed.cevap || '').trim();

if (!replyDraft || replyDraft.trim() === '') {
  if (caseType === 'exact_code_price_stock' || caseType === 'cross_reference') {
    replyDraft = 'Talebiniz alinmistir. Guncel stok ve fiyat kontrolu yapilarak size bilgi verilecektir.';
  } else if (caseType === 'exact_code_compatibility') {
    replyDraft = 'Arac uyumluluk kontrolunuz ilgili birimimize iletilmistir, yetkilimiz tarafindan bilgilendirileceksiniz.';
  } else if (caseType === 'partial_code') {
    replyDraft = 'Iletmis oldugunuz kod tam olarak anlasilamadi veya eksik. Filtre kodunun tamamini veya aracinizin detaylarini paylasabilir misiniz?';
  } else if (caseType === 'greeting') {
    replyDraft = 'Merhaba! Size nasil yardimci olabilirim? (Lutfen filtre kodunuzu veya aracinizin motor hacmi ve beygir gucu/sasi numarasini belirtin)';
  } else if (caseType === 'unclear') {
    replyDraft = 'Ifadenizi tam anlayamadim, ilgili uzmanimiza aktariyoruz.';
  } else {
    replyDraft = 'Talebiniz musteri temsilcimiz aktarilmistir.';
  }
}
const missingFields = Array.isArray(parsed.missingFields) ? parsed.missingFields.slice(0, 10) : [];
const verification = parsed.verification || {};

if (entities.quantity && entities.quantity !== 'Belirtilmedi') {
  const nums = String(entities.quantity).match(/\\d+/g);
  if (nums && nums.length > 0) {
    const num = nums[0];
    const qtyRegex = new RegExp('\\\\b' + num + '\\\\s*(?:adet|tane|pcs|x)|(?:x)\\\\s*' + num + '\\\\b', 'i');
    const textHasNumContext = qtyRegex.test(allMessagesText);
    if (!textHasNumContext) entities.quantity = 'Belirtilmedi';
  }
}

if (Array.isArray(entities.vehicles)) {
  entities.vehicles = entities.vehicles.map(v => {
    const textLower = allMessagesText.toLowerCase();
    if (typeof v === 'object' && v) {
      if (v.brand && !textLower.includes(String(v.brand).toLowerCase())) v.brand = null;
      if (v.model && !textLower.includes(String(v.model).toLowerCase())) v.model = null;
      if (v.year && !allMessagesText.includes(String(v.year))) v.year = null;
      if (v.engine && !textLower.includes(String(v.engine).toLowerCase())) v.engine = null;
      if (v.horsePower && !textLower.includes(String(v.horsePower).toLowerCase())) v.horsePower = null;
      if (v.vin && !textLower.includes(String(v.vin).toLowerCase())) v.vin = null;
      if (!v.brand && !v.model && !v.year && !v.engine && !v.vin && !v.raw) return null;
      if (v.raw) {
        const yearMatch = String(v.raw).match(/\\b(19\\d\\d|20\\d\\d)\\b/);
        if (yearMatch && !allMessagesText.includes(yearMatch[1])) v.raw = null;
        const rawWords = String(v.raw).toLowerCase().replace(/[^a-z0-9]/g, ' ').split(/\\s+/).filter(w => w.length > 2);
        if (v.raw && rawWords.length > 0 && !rawWords.every(w => textLower.includes(w))) v.raw = null;
      }
      return v;
    } else {
      let str = String(v);
      const yearMatch = str.match(/\\b(19\\d\\d|20\\d\\d)\\b/);
      if (yearMatch && !allMessagesText.includes(yearMatch[1])) return null;
      const engineMatch = str.match(/\\b(\\d\\.\\d)\\b/);
      if (engineMatch && !allMessagesText.includes(engineMatch[1])) return null;
      const words = str.toLowerCase().replace(/[^a-z0-9]/g, ' ').split(/\\s+/).filter(w => w.length > 2);
      if (words.length > 0 && !words.every(w => textLower.includes(w))) return null;
      return v;
    }
  }).filter(Boolean);
}

const knownBrands = ['MANN', 'BOSCH', 'FILTRON', 'UFI', 'HENGST', 'PURFLUX', 'MAHLE', 'FILTORQ'];
const textUpper = allMessagesText.toUpperCase();
const detectedBrands = knownBrands.filter(b => textUpper.includes(b));
if (detectedBrands.length > 0) {
  let existing = Array.isArray(entities.preferredBrands) ? entities.preferredBrands : [];
  entities.preferredBrands = [...new Set([...existing.map(x=>String(x).toUpperCase()), ...detectedBrands])];
}

const validCaseTypes = [
  'exact_code_price_stock',
  'exact_code_compatibility',
  'cross_reference',
  'partial_code',
  'non_product',
  'unclear',
  'greeting'
];

let isSchemaViolation = false;
if (!validCaseTypes.includes(caseType)) {
  isSchemaViolation = true;
  caseType = 'unclear';
}

let confidenceValue = 0;
const rawConfidence = parsed.confidence;
if (typeof rawConfidence === 'number' && Number.isFinite(rawConfidence)) {
  confidenceValue = rawConfidence;
} else if (typeof rawConfidence === 'object' && rawConfidence !== null) {
  const vals = [
    Number(rawConfidence.intent || 0),
    Number(rawConfidence.caseType || 0),
    Number(rawConfidence.entityExtraction || 0)
  ].filter(v => Number.isFinite(v));
  confidenceValue = vals.length > 0 ? Math.min(...vals) : 0;
}
confidenceValue = Math.max(0, Math.min(1, confidenceValue));

const hasExternalVerification = Boolean(currentInput?.externalVerificationVerified === true);
if (!hasExternalVerification) {
  verification.priceVerified = false;
  verification.stockVerified = false;
  verification.compatibilityVerified = false;
  verification.catalogVerified = false;
  verification.dataSource = 'unverified_ai_output';
}

let guardrailTriggered = false;
let triggeredRule = '';

const PRICE_PATTERN = /(?:₺\\s*\\d+(?:[\\.,]\\d+)?|\\d+(?:[\\.,]\\d+)?\\s*(?:TL|₺|TRY|Lira)|(?:fiyat|ucret|bedel|tutar)\\s*[:=]?\\s*\\d{2,}|(?:yuz|bin|milyon)\\s+(?:lira|tl))/i;
const COMPAT_GUARANTEE = /(?:(?:kesin(?:likle)?|garanti|tam(?:amen)?|net|birebir|%100|%99)\\s*(?:uy(?:ar|umlu|um|gundur)?|olur|oturur|takilir|gecer)|(?:arac|motor|model)\\s+(?:tam\\s+)?(?:uyar|uygundur|uyumludur|olur)|\\b(?:uygundur|uyumludur)\\b)/i;
const STOCK_GUARANTEE = /(?:stok(?:ta|larimizda|umuzda|larda)?|elimizde|depo(?:muz)?da)\\s+(?:mevcut(?:tur|dur)?|var(?:dir)?|bulun(?:uyor|maktadir)|uygun(?:dur)?|mevcuttur)/i;
const BANNED_PHRASES = [
  'stokta var', 'stoklarimizda mevcut', 'elimizde mevcut',
  'kesin uyar', 'uyumludur', 'uygundur',
  'araciniza uyar', 'aracinizla uyumludur', 'araciniz icin uygundur',
  'birebir muadilidir', 'yerine kullanabilirsiniz',
  'garanti uyar', 'garanti uygundur', 'mevcut gorunuyor',
  'sorunsuz kullanabilirsiniz', 'birebir karsiligidir',
  'tam karsiligidir', 'direkt takilir', 'rahatlikla kullanabilirsiniz'
];

const UNSAFE_CONTENT = /(?:https?:\\/\\/|www\\.)[^\\s]+|sifre|kredi\\s?kart|\\bcvv\\b|\\botp\\b/i;
if (UNSAFE_CONTENT.test(replyDraft)) {
  guardrailTriggered = true;
  triggeredRule = 'Guvenli olmayan baglanti veya hassas veri talebi';
} else if (verification.priceVerified !== true && PRICE_PATTERN.test(replyDraft)) {
  guardrailTriggered = true;
  triggeredRule = 'Dogrulanmamis rakamsal fiyat/TL halusinasyonu';
} else if (verification.stockVerified !== true || verification.compatibilityVerified !== true) {
  if (COMPAT_GUARANTEE.test(replyDraft) || STOCK_GUARANTEE.test(replyDraft)) {
    guardrailTriggered = true;
    triggeredRule = 'Yasakli stok/uyumluluk garantisi';
  } else {
    const replyLower = replyDraft.toLocaleLowerCase('tr-TR');
    for (const phrase of BANNED_PHRASES) {
      if (replyLower.includes(phrase.toLocaleLowerCase('tr-TR'))) {
        guardrailTriggered = true;
        triggeredRule = 'Yasakli stok/uyumluluk garantisi (' + phrase + ')';
        break;
      }
    }
  }
}

if (guardrailTriggered) {
  replyDraft = 'Urunun guncel stok, fiyat ve teknik uygunluk bilgisi yetkilimiz tarafindan kontrol edilerek size iletilecektir.';
}

const extractedCodeItems = Array.isArray(entities.productCodes) ? entities.productCodes : [];
if (extractedCodeItems.length > 0) {
  const rawCodes = extractedCodeItems.map(c => typeof c === 'object' ? (c.code || c.raw) : c).filter(Boolean);
  const sorted = [...new Set(rawCodes)].sort((a, b) => String(b).length - String(a).length);
  const deduped = [];
  for (const c of sorted) {
    if (!deduped.some(selected => String(selected).includes(String(c)))) deduped.push(c);
  }
  entities.productCodes = deduped;
}
let provenanceViolation = false;
let unverifiedCode = '';

if (extractedCodeItems.length > 0 && intent !== 'greeting' && caseType !== 'greeting') {
  const normalizeForMatch = (str) => String(str || '').replace(/[\\s\\-\\/\\._\\\\]+/g, '').toLocaleLowerCase('tr-TR');
  const normAllMessages = normalizeForMatch(allMessagesText);
  const normDetected = (Array.isArray(detectedCodes) ? detectedCodes : []).map(c => normalizeForMatch(c));

  for (const item of extractedCodeItems) {
    const rawVal = typeof item === 'object' && item !== null ? String(item.raw || '') : String(item || '');
    const codeVal = typeof item === 'object' && item !== null ? String(item.code || '') : String(item || '');

    const candidates = [rawVal, codeVal].filter(s => s && s.trim().length >= 3);
    if (candidates.length === 0) continue;

    let isProven = false;
    for (const cand of candidates) {
      const normCand = normalizeForMatch(cand);
      if (!normCand || normCand.length < 3) continue;

      if (allMessagesText.toLocaleLowerCase('tr-TR').includes(cand.toLocaleLowerCase('tr-TR')) ||
          normAllMessages.includes(normCand)) {
        isProven = true;
        break;
      }

      if (normDetected.some(d => d.includes(normCand) || normCand.includes(d))) {
        isProven = true;
        break;
      }
    }

    if (!isProven) {
      provenanceViolation = true;
      unverifiedCode = candidates[0] || 'Bilinmeyen Kod';
      break;
    }
  }
}

function isVehicleComplete(vehicles) {
  if (!Array.isArray(vehicles) || vehicles.length === 0) return false;
  const vinStringMatch = /\\b[A-HJ-NPR-Z0-9]{17}\\b/i;
  const engineRegex = /(?:\\b\\d+[\\.,]\\d+\\s*(?:tdi|tsi|cdti|hdi|tdci|mjet|tfsi|vvt-i|l|lt|cc)?\\b|\\b\\d+\\s*(?:hp|bg|ps|kw|cc)\\b|\\b(?:tdi|tsi|cdti|hdi|tdci|mjet|tfsi)\\b)/i;

  for (const v of vehicles) {
    if (typeof v === 'string') {
      const trimmed = v.trim();
      if (vinStringMatch.test(trimmed)) return true;
      const hasYear = /\\b(?:19|20)\\d{2}\\b/.test(trimmed);
      const hasEngine = engineRegex.test(trimmed);
      const words = trimmed.split(/\\s+/).filter(Boolean);
      if (hasYear && hasEngine && words.length >= 4) return true;
    } else if (typeof v === 'object' && v !== null) {
      const vin = String(v.vin || v.chassis || v.sasi || '').trim();
      if (vin.length === 17 || vinStringMatch.test(vin)) return true;
      const fullObjStr = Object.values(v).join(' ');
      if (vinStringMatch.test(fullObjStr)) return true;
      const brand = String(v.brand || v.marka || '').trim();
      const model = String(v.model || '').trim();
      const year = String(v.year || v.yil || '').trim();
      const engine = String(v.engine || v.motor || v.engineCode || v.motorKodu || v.hp || v.power || v.cc || v.spec || '').trim();
      const hasBrandModelYear = Boolean(brand && model && year && /\\d{4}/.test(year));
      const hasEngineSpec = Boolean(engine) || engineRegex.test(fullObjStr);
      if (hasBrandModelYear && hasEngineSpec) return true;
    }
  }
  return false;
}

let requiresHumanAction = false;
let notifyAdmin = false;
let pauseAutomation = false;
let askVehicleInfo = false;
let action = 'reply';
let handoffReason = guardrailTriggered ? 'Guardrail Mudahalesi: ' + triggeredRule : '';

if (isSchemaViolation) {
  requiresHumanAction = true;
  notifyAdmin = true;
  pauseAutomation = true;
  action = 'handoff';
  handoffReason = 'Sema Ihlali: Tanimsiz/Uydurma Case Type engellendi (' + String(parsed.caseType || 'bos') + ' -> unclear)';
  replyDraft = 'Talebinizi dogru yonlendirebilmek icin ilgili ekibimize aktariyoruz. Yetkilimiz sizinle ilgilenecektir.';
} else if (provenanceViolation) {
  requiresHumanAction = true;
  notifyAdmin = true;
  pauseAutomation = true;
  action = 'handoff';
  handoffReason = 'Katalog/Mesaj disi parcakodu uydurma suphesi (Provenance: ' + unverifiedCode + ')';
  replyDraft = 'Parca kodunuzu ve arac uyumlulugunu netlestirmek uzere talebinizi yetkilimize aktariyoruz.';
  if (Array.isArray(entities.productCodes)) {
    entities.productCodes = entities.productCodes.filter(c => {
      const v = typeof c === 'object' && c !== null ? String(c.raw || c.code || '') : String(c || '');
      return !v.includes(unverifiedCode) && !unverifiedCode.includes(v);
    });
  }
} else if (confidenceValue < 0.55 && intent !== 'greeting' && intent !== 'unclear') {
  requiresHumanAction = true;
  notifyAdmin = true;
  pauseAutomation = true;
  action = 'handoff';
  handoffReason = handoffReason || 'Dusuk guven skoru (' + confidenceValue.toFixed(2) + ')';
  replyDraft = 'Talebinizi ilgili ekibimize aktariyoruz. Yetkilimiz sizinle ilgilenecektir.';
} else if (guardrailTriggered) {
  requiresHumanAction = true;
  notifyAdmin = true;
  pauseAutomation = false;
} else if (caseType === 'exact_code_price_stock') {
  requiresHumanAction = true;
  notifyAdmin = true;
  pauseAutomation = false;
  askVehicleInfo = false;
  replyDraft = 'Talebiniz alinmistir. Stok ve net fiyat bilgisi en gec 5 dakika icinde paylasilacaktir.';
} else if (caseType === 'exact_code_compatibility') {
  if (!isVehicleComplete(entities.vehicles)) {
    requiresHumanAction = false;
    notifyAdmin = true;
    pauseAutomation = false;
    askVehicleInfo = true;
    action = 'reply';
    replyDraft = 'Arac uyumlulugunun kesin tespiti icin lutfen aracinizin motor hacmini (orn: 1.6 TDI) ve beygir gucunu (veya sasi numarasini) belirtebilir misiniz?';
  } else {
    requiresHumanAction = true;
    notifyAdmin = true;
    pauseAutomation = false;
    askVehicleInfo = false;
  }
} else if (caseType === 'cross_reference') {
  requiresHumanAction = true;
  notifyAdmin = true;
  pauseAutomation = false;
  askVehicleInfo = false;
  const sourceCode = (entities.productCodes && entities.productCodes.length > 0) ? (entities.productCodes[0].code || entities.productCodes[0].raw || entities.productCodes[0]) : 'Belirtilen';
  const prefBrands = (entities.preferredBrands && entities.preferredBrands.length > 0) ? entities.preferredBrands.join(' veya ') : 'muadil';
  replyDraft = sourceCode + ' kodu icin ' + prefBrands + ' talebinizi aldim. Yanlis parca yonlendirmemek icin muadil kodu uretici katalogundan teyit ederek paylasacagiz. Yetkilimiz kontrol sonrasi size donus yapacaktir.';
} else if (caseType === 'partial_code') {
  requiresHumanAction = false;
  notifyAdmin = false;
  pauseAutomation = false;
} else if (caseType === 'non_product' || intent === 'return_complaint' || intent === 'wholesale') {
  const complaintKeywords = ['sikayet', 'iade', 'geri', 'para iadesi', 'bozuk', 'hasarli', 'kirik', 'yanlis', 'eksik', 'sorunlu', 'memnun degil', 'bayilik', 'temsilci', 'kargo', 'gelmedi', 'ulasamadi', 'siparis', 'odeme', 'cekildi', 'iptal', 'degisim', 'yetkili', 'canli destek', 'insan', 'gorusmek'];
  const hasComplaintKeyword = complaintKeywords.some(kw => allMessagesText.toLowerCase().includes(kw));
  if (!hasComplaintKeyword) {
    caseType = 'unclear';
    action = 'reply';
    notifyAdmin = false;
    pauseAutomation = false;
    requiresHumanAction = false;
    replyDraft = 'Hangi konuda yardimci olabilirim? Filtre mi ariyorsunuz, yoksa baska bir talebiniz mi var?';
    handoffReason = '';
  } else {
    requiresHumanAction = true;
    notifyAdmin = true;
    pauseAutomation = true;
    action = 'handoff';
    handoffReason = 'Ozel durum veya temsilci talebi (' + intent + ')';
  }
} else if (caseType === 'unclear') {
  staticData._unclearCounts[senderNumber] = Number(staticData._unclearCounts[senderNumber] || 0) + 1;
  if (staticData._unclearCounts[senderNumber] >= 2) {
    requiresHumanAction = true;
    notifyAdmin = true;
    pauseAutomation = true;
    action = 'handoff';
    handoffReason = 'Talep 2 kez ust uste anlasilamadi';
    replyDraft = 'Talebinizi dogru yonlendirebilmek icin ilgili ekibimize aktariyoruz. Yetkilimiz sizinle ilgilenecektir.';
  }
} else if (caseType === 'greeting') {
  requiresHumanAction = false;
  notifyAdmin = false;
  pauseAutomation = false;
}

if (caseType !== 'unclear' && !isSchemaViolation) delete staticData._unclearCounts[senderNumber];

const now = Date.now();
const lastNotif = staticData._adminNotifications[senderNumber];
let isUpdate = false;
let shouldNotifyAdmin = notifyAdmin;

const notifKeys = Object.keys(staticData._adminNotifications);
if (notifKeys.length > 500) {
  const sorted = notifKeys.sort((a, b) =>
    (staticData._adminNotifications[a].timestamp || 0) -
    (staticData._adminNotifications[b].timestamp || 0)
  );
  sorted.slice(0, sorted.length - 300).forEach(k => delete staticData._adminNotifications[k]);
}

const currentCodes = Array.isArray(entities.productCodes) ? entities.productCodes.map(c => typeof c === 'object' ? c.code || c.raw : c).filter(Boolean) : [];
const currentVehicles = Array.isArray(entities.vehicles) ? entities.vehicles.map(v => typeof v === 'object' ? ((v.brand||'') + ' ' + (v.model||'') + ' ' + (v.year||'') + ' ' + (v.engine||'')).trim() : String(v)).filter(Boolean) : [];
const currentBrands = Array.isArray(entities.preferredBrands) ? entities.preferredBrands : [];
const quantity = String(entities.quantity || 'Belirtilmedi');

if (notifyAdmin && lastNotif && (now - Number(lastNotif.timestamp) < 3 * 60 * 1000)) {
  const oldCodes = lastNotif.codes || [];
  const oldVehicles = lastNotif.vehicles || [];
  const oldBrands = lastNotif.brands || [];
  const addedCodes = currentCodes.filter(c => !oldCodes.includes(c));
  const addedVehicles = currentVehicles.filter(v => !oldVehicles.includes(v));
  const addedBrands = currentBrands.filter(b => !oldBrands.includes(b));
  const qtyChanged = lastNotif.quantity !== quantity && quantity !== 'Belirtilmedi';
  if (addedCodes.length > 0 || addedVehicles.length > 0 || addedBrands.length > 0 || qtyChanged || caseType !== lastNotif.caseType) {
    isUpdate = true;
    shouldNotifyAdmin = true;
  } else {
    shouldNotifyAdmin = false;
  }
}

let headerTitle = '';
if (caseType === 'non_product' || action === 'handoff') {
  headerTitle = 'SIKAYET / IADE / TEMSILCI TALEBI';
} else if (caseType === 'exact_code_compatibility' || intent === 'product_compatibility') {
  headerTitle = 'UYUMLULUK VE PARCA KONTROLU';
} else if (caseType === 'cross_reference') {
  headerTitle = 'MUADIL / CAPRAZ REFERANS TALEBI';
} else if (caseType === 'exact_code_price_stock' || currentCodes.length > 0) {
  headerTitle = 'YUKSEK NIYETLI SATIS TALEBI';
} else {
  headerTitle = 'MUSTERI TALEBI / BILDIRIM';
}

if (isUpdate) {
  headerTitle = 'SATIS TALEBI GUNCELLENDI';
}

const formattedCodes = currentCodes.length > 0 ? currentCodes.map(c => c).join(' ') : 'Belirtilmedi';
const codeStr = provenanceViolation ? 'SUPHELI AI KODU: ' + unverifiedCode + ' Temizlenen Kodlar: ' + formattedCodes : formattedCodes;
const formattedVehicles = Array.isArray(entities.vehicles) && entities.vehicles.length > 0 ? entities.vehicles.map(v => typeof v === 'object' ? ((v.brand || '') + ' ' + (v.model || '') + ' ' + (v.year || '')).trim() : String(v)).join(' ') : (caseType === 'exact_code_price_stock' ? 'Gerekli degil (Tam kod verildi)' : 'Belirtilmedi');

const bildirim = headerTitle + '\\n' +
  'SLA: 5 dk\\n\\n' +
  senderName + '\\n' +
  senderNumber + '\\n\\n' +
  'Urun/Kod\\n' + codeStr + '\\n\\n' +
  'Arac\\n' + formattedVehicles + '\\n\\n' +
  'Istenen\\n- Stok\\n- Net fiyat\\n- Bugun kargo\\n\\n' +
  'Atanan\\nIsmail Ozkaracan\\n\\n' +
  '--------------\\n\\n' +
  'Musteri\\n"' + allMessagesText + '"\\n\\n' +
  'AI musteriye gonderdi\\n"' + replyDraft + '"' +
  (handoffReason ? '\\n\\nHandoff Nedeni: ' + handoffReason : '');

if (!staticData._manualModes) staticData._manualModes = {};
if (action === 'handoff' || pauseAutomation === true) {
  staticData._manualModes[senderNumber] = { enabled: true, createdAt: Date.now() };
}

const bildirimFinal = bildirim;

if (shouldNotifyAdmin === true) {
  staticData._adminNotifications[senderNumber] = {
    timestamp: now,
    codes: currentCodes,
    vehicles: currentVehicles,
    brands: currentBrands,
    quantity,
    caseType
  };
  staticData._adminNotifications = Object.assign({}, staticData._adminNotifications);
}

if (staticData._batches && staticData._batches[senderNumber]) {
  const batchToClose = staticData._batches[senderNumber];
  batchToClose.processingMessages = [];
  batchToClose.processing = false;
  batchToClose.processingToken = null;
  batchToClose.processingStartedAt = null;
  if (!Array.isArray(batchToClose.pendingMessages) || batchToClose.pendingMessages.length === 0) {
    delete staticData._batches[senderNumber];
  }
  staticData._batches = Object.assign({}, staticData._batches);
}
if (action === 'reply' && Boolean(parsed.expectsReply === true || askVehicleInfo === true) && !pauseAutomation && senderNumber) {
  if (!staticData._lastReply) staticData._lastReply = {};
  staticData._lastReply[senderNumber] = Date.now();
  staticData._lastReply = Object.assign({}, staticData._lastReply);
}

return {
  json: {
    senderNumber,
    senderName,
    batchToken,
    action,
    intent,
    caseType,
    entities,
    cevap: replyDraft,
    bildirim: bildirimFinal,
    missingFields,
    handoffReason,
    requiresHumanAction,
    pauseAutomation,
    notifyAdmins: shouldNotifyAdmin === true,
    askVehicleInfo: Boolean(askVehicleInfo === true),
    expectsReply: Boolean(parsed.expectsReply === true || askVehicleInfo === true),
    validClaim: true,
    isSchemaViolation,
    guardrailTriggered,
    triggeredRule,
    verification,
    provenanceViolation,
    unverifiedCode,
    confidence: confidenceValue
  }
};
`;

function runPolicyEngine(staticData, inputJson, storeContextJson) {
  const storeContext = mockStoreContext(storeContextJson);

  const _dollar = (nodeName) => {
    if (nodeName === 'Store Context') return storeContext;
    throw new Error('Unknown node: ' + nodeName);
  };

  const mockStaticDataFn = (scope) => {
    if (scope !== 'global') throw new Error('Only global scope supported in tests');
    return staticData;
  };

  const mockInput = { item: { json: inputJson } };

  // Inject mocks as globals via arguments
  const wrapperCode =
    'var $getWorkflowStaticData = arguments[0];\n' +
    'var $input = arguments[1];\n' +
    'var $ = arguments[2];\n' +
    parseAiOutputJs;

  const fn = new Function(wrapperCode);

  try {
    const result = fn(mockStaticDataFn, mockInput, _dollar);
    return result;
  } catch (error) {
    console.error('[Test Harness] Error:', error);
    throw error;
  }
}

module.exports = { createStaticData, runPolicyEngine };
