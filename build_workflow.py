import json
import uuid

# ── Node IDs (stable, reused from n8n) ──
node_ids = {
    "Webhook1": "65f757d5-7045-45df-90aa-a959a4a10519",
    "Respond OK1": "c370ae94-67de-411e-8368-4d479f00e421",
    "fromMe Check": "5527d4b8-019e-4bb6-bbd3-526fab1f9470",
    "Batch Collector": "cf3dc39b-5fa7-5389-ac72-94e2862a9cc2",
    "Should Process?": "6d6eba4b-4ded-5387-8f29-7d518c86632f",
    "Is Command?": "cc-001-cmd-check",
    "Store Context": "d7ae6ef8-a8e2-5779-a8fb-7a98a18f48c3",
    "AI Agent": "9409b931-1973-4c94-9d6e-5c255f6ee037",
    "OpenAI Chat Model1": "1b7c08e5-1da2-4a07-b017-370d41c50e85",
    "Simple Memory": "8627d7e8-8bc2-4449-b79b-dd1a4c04c32d",
    "Parse AI Output": "64249ad4-6e81-5542-bfda-6929c6c28aa6",
    "Clear Batch": "77f0e3d1-9d66-5d9b-a5b4-d30379bc9dd1",
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
    "const input = $input.first().json;\n"
    "\n"
    "const rawJid = input.body.data.key.remoteJid || '';\n"
    "const senderNumber = rawJid.replace('@s.whatsapp.net', '').replace('@g.us', '');\n"
    "const senderName = input.body.data.pushName || senderNumber;\n"
    "const messageText = (input.body.data.message?.conversation\n"
    "  || input.body.data.message?.extendedTextMessage?.text\n"
    "  || '[Medya]').trim();\n"
    "\n"
    "const fromMe = input.body.data.key.fromMe === true;\n"
    "const now = Date.now();\n"
    "const windowMs = 3 * 60 * 1000;\n"
    "const maxMessages = 30;\n"
    "\n"
    "if (!staticData._batches) staticData._batches = {};\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n"
    "\n"
    "// === ++/-- KOMUTLARI: HER ZAMAN KOMUT OLARAK ISLE ===\n"
    "// fromMe kontrolu yapilmaz, sadece mesaj icerigine bakilir\n"
    "if (messageText === '++') {\n"
    "  staticData._manualModes[senderNumber] = true;\n"
    "  delete staticData._batches[senderNumber];\n"
    "  return [{ json: {\n"
    "    _action: 'command',\n"
    "    senderNumber: senderNumber,\n"
    "    command: 'paused',\n"
    "    bildirim: 'Sistem Manuel De - ' + senderName + ' (' + senderNumber + ')'\n"
    "  }}];\n"
    "}\n"
    "\n"
    "if (messageText === '--') {\n"
    "  staticData._manualModes[senderNumber] = false;\n"
    "  return [{ json: {\n"
    "    _action: 'command',\n"
    "    senderNumber: senderNumber,\n"
    "    command: 'resumed',\n"
    "    bildirim: 'Sistem Otomatik - ' + senderName + ' (' + senderNumber + ')'\n"
    "  }}];\n"
    "}\n"
    "\n"
    "// fromMe ve diger komutlari yut\n"
    "if (fromMe) {\n"
    "  return [{ json: { _action: 'ignore' } }];\n"
    "}\n"
    "\n"
    "// === MUSTERI MANUEL MODDA MI? ===\n"
    "if (staticData._manualModes[senderNumber] === true) {\n"
    "  return [{ json: { _action: 'ignore' } }];\n"
    "}\n"
    "\n"
    "// === BATCH TOPLAMA ===\n"
    "if (!staticData._batches[senderNumber]) {\n"
    "  staticData._batches[senderNumber] = {\n"
    "    messages: [],\n"
    "    startTime: now,\n"
    "    lastMessageTime: now,\n"
    "    senderName: senderName,\n"
    "    processing: false\n"
    "  };\n"
    "}\n"
    "\n"
    "const batch = staticData._batches[senderNumber];\n"
    "\n"
    "// KRITIK: AI isliyorsa mesaji ekle ama tetikleme\n"
    "if (batch.processing) {\n"
    "  if (batch.messages.length < maxMessages) {\n"
    "    batch.messages.push({ text: messageText,"
    "      time: new Date(now).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) });\n"
    "    batch.lastMessageTime = now;\n"
    "    batch.senderName = senderName;\n"
    "  }\n"
    "  return [{ json: { _action: 'queued_during_processing' } }];\n"
    "}\n"
    "\n"
    "// Spam korumasi\n"
    "if (batch.messages.length >= maxMessages) {\n"
    "  return [{ json: { _action: 'spam_limit' } }];\n"
    "}\n"
    "\n"
    "batch.messages.push({ text: messageText,"
    "  time: new Date(now).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) });\n"
    "batch.lastMessageTime = now;\n"
    "batch.senderName = senderName;\n"
    "\n"
    "// SLIDING WINDOW: son mesajdan itibaren 3 dk\n"
    "const idleTime = now - batch.lastMessageTime;\n"
    "const batchReady = idleTime >= windowMs;\n"
    "\n"
    "if (batchReady) {\n"
    "  batch.processing = true;\n"
    "}\n"
    "\n"
    "const allMessagesText = batch.messages.map((m, i) => `${i + 1}. [${m.time}] ${m.text}`).join('\\n');\n"
    "\n"
    "return [{\n"
    "  json: {\n"
    "    _action: batchReady ? 'process' : 'wait',\n"
    "    senderNumber,\n"
    "    senderName: batch.senderName,\n"
    "    messageCount: batch.messages.length,\n"
    "    batchReady,\n"
    "    allMessagesText\n"
    "  }\n"
    "}];"
)

store_context_js = (
    "const input = $input.first().json;\n"
    "return [{\n"
    "  json: {\n"
    "    senderNumber: input.senderNumber,\n"
    "    senderName: input.senderName,\n"
    "    allMessagesText: input.allMessagesText,\n"
    "    messageCount: input.messageCount,\n"
    "    _prompt: `Gonderen: ${input.senderName} (${input.senderNumber})\\n"
    "Mesaj sayisi: ${input.messageCount}\\n\\n"
    "Mesajlar:\\n${input.allMessagesText}`\n"
    "  }\n"
    "}];"
)

parse_ai_output_js = (
    "const aiOutput = $input.first().json?.output || '';\n"
    "\n"
    "let senderNumber = '';\n"
    "let senderName = '';\n"
    "let allMessagesText = '';\n"
    "try {\n"
    "  const sc = $('Store Context').item.json;\n"
    "  senderNumber = sc.senderNumber || '';\n"
    "  senderName = sc.senderName || '';\n"
    "  allMessagesText = sc.allMessagesText || '';\n"
    "} catch (e) {}\n"
    "\n"
    "let bildirim = '';\n"
    "let cevap = 'Talebinizi aldim, en kisa surede donecegiz.';\n"
    "\n"
    "try {\n"
    "  const jsonMatch = aiOutput.match(/\\{[\\s\\S]*\\}/);\n"
    "  if (jsonMatch) {\n"
    "    const parsed = JSON.parse(jsonMatch[0]);\n"
    "    bildirim = parsed.bildirim || '';\n"
    "    cevap = parsed.cevap || cevap;\n"
    "  }\n"
    "} catch (e) {}\n"
    "\n"
    "if (!bildirim) {\n"
    "  bildirim = `${senderName} ${senderNumber} - ${allMessagesText.substring(0, 80)}`;\n"
    "}\n"
    "\n"
    "const detayliBildirim = `YENI MESAJ - filtreto.com\\n"
    "Gonderen: ${senderName}\\n"
    "Numara: ${senderNumber}\\n"
    "Ozet: ${bildirim}\\n"
    "\\n"
    "Musteriye Gonderilen Yanit:\\n"
    "${cevap}`;\n"
    "\n"
    "return [{\n"
    "  json: {\n"
    "    bildirim: detayliBildirim,\n"
    "    cevap,\n"
    "    senderNumber,\n"
    "    senderName\n"
    "  }\n"
    "}];"
)

clear_batch_js = (
    "const input = $input.first().json;\n"
    "const staticData = $getWorkflowStaticData('global');\n"
    "\n"
    "const senderNumber = input.senderNumber;\n"
    "if (staticData._batches && senderNumber) {\n"
    "  delete staticData._batches[senderNumber];\n"
    "}\n"
    "\n"
    "return [{ json: input }];"
)

stale_batch_check_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const now = Date.now();\n"
    "const windowMs = 3 * 60 * 1000;\n"
    "\n"
    "if (!staticData._batches) staticData._batches = {};\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n"
    "\n"
    "const results = [];\n"
    "\n"
    "for (const [number, batch] of Object.entries(staticData._batches)) {\n"
    "  if (staticData._manualModes[number] === true) {\n"
    "    delete staticData._batches[number];\n"
    "    continue;\n"
    "  }\n"
    "  \n"
    "  if (batch.processing) continue;\n"
    "  \n"
    "  const lastTime = batch.lastMessageTime || batch.startTime;\n"
    "  const idleTime = now - lastTime;\n"
    "\n"
    "  if (idleTime >= windowMs && batch.messages.length > 0) {\n"
    "    batch.processing = true;\n"
    "    const allMessagesText = batch.messages.map((m, i) => `${i + 1}. [${m.time}] ${m.text}`).join('\\n');\n"
    "    results.push({\n"
    "      json: {\n"
    "        senderNumber: number,\n"
    "        senderName: batch.senderName,\n"
    "        messageCount: batch.messages.length,\n"
    "        allMessagesText\n"
    "      }\n"
    "    });\n"
    "  }\n"
    "}\n"
    "\n"
    "if (results.length === 0) {\n"
    "  return [{ json: { senderNumber: '', messageCount: 0 } }];\n"
    "}\n"
    "\n"
    "return results;"
)

idle_timeout_check_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const now = Date.now();\n"
    "const idleAlertMs = 10 * 60 * 1000;\n"
    "\n"
    "if (!staticData._lastReply) staticData._lastReply = {};\n"
    "\n"
    "const alerts = [];\n"
    "for (const [number, lastReplyTime] of Object.entries(staticData._lastReply)) {\n"
    "  if (now - lastReplyTime >= idleAlertMs) {\n"
    "    alerts.push({\n"
    "      json: {\n"
    "        senderNumber: number,\n"
    "        bildirim: `Sessiz musteri - ${number} - 10 dkdir cevap yazmiyor`,\n"
    "        _idleAlert: true\n"
    "      }\n"
    "    });\n"
    "    delete staticData._lastReply[number];\n"
    "  }\n"
    "}\n"
    "\n"
    "if (alerts.length === 0) {\n"
    "  return [{ json: { _idleAlert: false } }];\n"
    "}\n"
    "return alerts;"
)

ai_agent_system_message = (
    "Sen filtreto.com WhatsApp asistanisin. FiltreOto; Ankara merkezli, orijinal MANN-Filter, "
    "FILTRON, FILTORQ, UFI FILTRE, Bosch, Wunder ve Sampiyon gibi markalarin yag, hava, yakit "
    "ve polen filtrelerinin/setlerinin satisini yapan kurumsal bir e-ticaret platformudur. "
    "Musterilere orijinal urun garantisi, hizli kargo ve sase numarasi ile uyumluluk kontrolu sunar. "
    "Kisa ve oz yazarsin.\n\n"
    "SADECE su JSON'u dondur, baska bir sey yazma:\n"
    '{"bildirim":"KISA bildirim","cevap":"KISA cevap"}\n\n'
    "bildirim formati (MUTLAKA bu formatta, tek blok, emoji kullanma):\n"
    "[isim] [numara] - [mesajin ozeti 5-10 kelime]\n\n"
    "cevap formati:\n"
    "- Sadece 1-2 cumle, maksimum 30 kelime\n"
    "- Selam verme, direkt konuya gir\n"
    "- Turkce\n\n"
    "Ornekler:\n"
    '{"bildirim":"Ismail 905331112233 - Yag filtresi siparisi istiyor",'
    '"cevap":"Filtre uyumu icin aracinizin marka/model/yil/sase bilgisini paylasir misiniz?"}'
)

# ── Node Definitions ──
nodes = [
    {
        "parameters": {"httpMethod": "POST", "path": "evolution-webhook", "responseMode": "responseNode", "options": {}},
        "id": get_node_id("Webhook1"), "name": "Webhook1",
        "type": "n8n-nodes-base.webhook", "typeVersion": 1.1,
        "position": [240, 640], "webhookId": "b543e85d-b182-4ddd-af94-3f124a6c2c82"
    },
    {
        "parameters": {"respondWith": "json", "responseBody": "={\"status\":\"ok\"}", "options": {}},
        "id": get_node_id("Respond OK1"), "name": "Respond OK1",
        "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1, "position": [240, 432]
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [
                    {"id": "cond-allow", "leftValue": "={{ !$json.body.data.key.fromMe || ['++', '--'].includes($json.body.data.message?.conversation || $json.body.data.message?.extendedTextMessage?.text || '') }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}},
                    {"id": "cond-no-group", "leftValue": "={{ $json.body.data.key.remoteJid }}", "rightValue": "@g.us", "operator": {"type": "string", "operation": "notEndsWith"}}
                ],
                "combinator": "and"
            }, "options": {}
        },
        "id": get_node_id("fromMe Check"), "name": "fromMe Check",
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [528, 640]
    },
    {
        "parameters": {"jsCode": batch_collector_js},
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
        "parameters": {"jsCode": store_context_js},
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
            "builtInTools": {}, "options": {"temperature": 0.2, "maxTokens": 300}
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
        "parameters": {"jsCode": parse_ai_output_js},
        "id": get_node_id("Parse AI Output"), "name": "Parse AI Output",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1808, 624]
    },
    {
        "parameters": {"jsCode": clear_batch_js},
        "id": get_node_id("Clear Batch"), "name": "Clear Batch",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2032, 624]
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "089311B617B8-48CF-8BD6-29759A57FDBF"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905052237182', text: $json.bildirim }) }}",
            "options": {"timeout": 30000, "batching": {"batch": {"batchSize": 1, "batchInterval": 100}}}
        },
        "id": get_node_id("Phone A Send"), "name": "Phone A Send",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2288, 416]
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "089311B617B8-48CF-8BD6-29759A57FDBF"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905306056066', text: $json.bildirim }) }}",
            "options": {"timeout": 30000}
        },
        "id": get_node_id("Phone B Send"), "name": "Phone B Send",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2288, 640]
    },
    {
        "parameters": {
            "method": "POST", "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": "089311B617B8-48CF-8BD6-29759A57FDBF"},
                {"name": "Content-Type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: $json.senderNumber, text: $json.cevap }) }}",
            "options": {"timeout": 30000}
        },
        "id": get_node_id("Reply to Customer"), "name": "Reply to Customer",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [2288, 864]
    },
    {
        "parameters": {"rule": {"interval": [{"field": "seconds", "secondsInterval": 60}]}},
        "id": get_node_id("Schedule Trigger"), "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [240, 1104]
    },
    {
        "parameters": {"jsCode": stale_batch_check_js},
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
        "parameters": {"jsCode": idle_timeout_check_js},
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
]

# ── Connections ──
connections = {
    "Webhook1": {"main": [[{"node": "Respond OK1", "type": "main", "index": 0}, {"node": "fromMe Check", "type": "main", "index": 0}]]},
    "fromMe Check": {"main": [[{"node": "Batch Collector", "type": "main", "index": 0}], []]},
    "Batch Collector": {"main": [[{"node": "Should Process?", "type": "main", "index": 0}, {"node": "Is Command?", "type": "main", "index": 0}]]},
    "Should Process?": {"main": [[{"node": "Store Context", "type": "main", "index": 0}], []]},
    "Is Command?": {"main": [[{"node": "Phone A Send", "type": "main", "index": 0}, {"node": "Phone B Send", "type": "main", "index": 0}], []]},
    "Store Context": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
    "AI Agent": {"main": [[{"node": "Parse AI Output", "type": "main", "index": 0}]]},
    "Parse AI Output": {"main": [[{"node": "Clear Batch", "type": "main", "index": 0}]]},
    "Clear Batch": {"main": [[{"node": "Phone A Send", "type": "main", "index": 0}, {"node": "Phone B Send", "type": "main", "index": 0}, {"node": "Reply to Customer", "type": "main", "index": 0}]]},
    "Schedule Trigger": {"main": [[{"node": "Stale Batch Check", "type": "main", "index": 0}, {"node": "Idle Timeout Check", "type": "main", "index": 0}]]},
    "Stale Batch Check": {"main": [[{"node": "Stale Exists?", "type": "main", "index": 0}]]},
    "Stale Exists?": {"main": [[{"node": "Store Context", "type": "main", "index": 0}], []]},
    "Idle Timeout Check": {"main": [[{"node": "Idle Alert?", "type": "main", "index": 0}]]},
    "Idle Alert?": {"main": [[{"node": "Phone A Send", "type": "main", "index": 0}, {"node": "Phone B Send", "type": "main", "index": 0}], []]},
    "OpenAI Chat Model1": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
    "Simple Memory": {"ai_memory": [[{"node": "AI Agent", "type": "ai_memory", "index": 0}]]},
}

# ── Build ──
with open("workflow.json", "r", encoding="utf-8") as f:
    wf = json.load(f)

wf["nodes"] = nodes
wf["connections"] = connections
wf["settings"] = {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveExecutionProgress": True, "saveManualExecutions": True}
wf["staticData"] = {"node:Schedule Trigger": {"recurrenceRules": []}, "global": {"_batches": {}}}
wf["meta"] = {"templateCredsSetupCompleted": True}
wf["pinData"] = {}

with open("workflow.json", "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)

print(f"workflow.json v5 generated: {len(nodes)} nodes, {len(connections)} connection sources")
