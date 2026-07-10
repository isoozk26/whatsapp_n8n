import json
import uuid

# We reuse original IDs from workflow.json to keep n8n state stable
node_ids = {
    "Webhook1": "65f757d5-7045-45df-90aa-a959a4a10519",
    "Respond OK1": "c370ae94-67de-411e-8368-4d479f00e421",
    "fromMe Check": "5527d4b8-019e-4bb6-bbd3-526fab1f9470",
    "Batch Collector": "cf3dc39b-5fa7-5389-ac72-94e2862a9cc2",
    "Batch Ready?": "6d6eba4b-4ded-5387-8f29-7d518c86632f",
    "Store Context": "d7ae6ef8-a8e2-5779-a8fb-7a98a18f48c3",
    "Parse AI Output": "64249ad4-6e81-5542-bfda-6929c6c28aa6",
    "Clear Batch": "77f0e3d1-9d66-5d9b-a5b4-d30379bc9dd1",
    "AI Agent": "9409b931-1973-4c94-9d6e-5c255f6ee037",
    "OpenAI Chat Model1": "1b7c08e5-1da2-4a07-b017-370d41c50e85",
    "Simple Memory": "8627d7e8-8bc2-4449-b79b-dd1a4c04c32d",
    "Phone A Send": "61d75176-a426-41d9-8a8e-6d4c626f8df5",
    "Phone B Send": "e43d47e9-69fe-4bbd-9e59-59ccd0a31629",
    "Reply to Customer": "ad29ccfa-691f-584b-8212-198b25bbbc24",
    "Schedule Trigger": "0a90afa9-6731-5ce6-a4d0-76a4fc92898f",
    "Stale Batch Check": "7fa1b04c-9639-5b87-99e7-e21c1d1bfc3b",
    "Stale Exists?": "0304e900-4c6f-5cb7-a857-3c5f2e302d90",
    "Command Check": "cc-001-cmd-check",
}


def get_node_id(name):
    if name in node_ids:
        return node_ids[name]
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"n8n.workflow.filtreoto.{name}"))


# ── Batch Collector: manual mode toggle (++ / --) + batch collection ──
# Exact match with workflow.json - do not alter Turkish characters
batch_collector_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const input = $input.first().json;\n"
    "\n"
    "const rawJid = input.body.data.key.remoteJid || '';\n"
    "const senderNumber = rawJid.replace('@s.whatsapp.net', '').replace('@g.us', '');\n"
    "const senderName = input.body.data.pushName || senderNumber;\n"
    "const messageText = (input.body.data.message?.conversation\n"
    "  || input.body.data.message?.extendedTextMessage?.text\n"
    "  || '[Medya Mesajı]').trim();\n"
    "\n"
    "const fromMe = input.body.data.key.fromMe === true;\n"
    "const now = Date.now();\n"
    "const windowMs = 3 * 60 * 1000;\n"
    "\n"
    "if (!staticData._batches) staticData._batches = {};\n"
    "if (!staticData._manualModes) staticData._manualModes = {};\n"
    "\n"
    "// Handle commands from the owner (fromMe is true)\n"
    "if (fromMe) {\n"
    "  if (messageText === '++') {\n"
    "    staticData._manualModes[senderNumber] = true;\n"
    "    delete staticData._batches[senderNumber]; // Clear pending batch\n"
    "    return [{\n"
    "      json: {\n"
    "        _skip: true,\n"
    "        senderNumber,\n"
    "        command: 'paused',\n"
    "        bildirim: `Otomatik asistan ${senderName} (${senderNumber}) için DURDURULDU.`\n"
    "      }\n"
    "    }];\n"
    "  } else if (messageText === '--') {\n"
    "    staticData._manualModes[senderNumber] = false;\n"
    "    return [{\n"
    "      json: {\n"
    "        _skip: true,\n"
    "        senderNumber,\n"
    "        command: 'resumed',\n"
    "        bildirim: `Otomatik asistan ${senderName} (${senderNumber}) için tekrar AKTİF edildi.`\n"
    "      }\n"
    "    }];\n"
    "  }\n"
    "}\n"
    "\n"
    "// If this customer is in manual mode, skip auto-reply\n"
    "if (staticData._manualModes[senderNumber] === true) {\n"
    "  return [{\n"
    "    json: {\n"
    "      _skip: true,\n"
    "      senderNumber\n"
    "    }\n"
    "  }];\n"
    "}\n"
    "\n"
    "// Normal batch collection for customer messages\n"
    "if (!staticData._batches[senderNumber]) {\n"
    "  staticData._batches[senderNumber] = {\n"
    "    messages: [],\n"
    "    startTime: now,\n"
    "    senderName: senderName\n"
    "  };\n"
    "}\n"
    "\n"
    "staticData._batches[senderNumber].messages.push({\n"
    "  text: messageText,\n"
    "  time: new Date(now).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })\n"
    "});\n"
    "\n"
    "staticData._batches[senderNumber].senderName = senderName;\n"
    "\n"
    "const batch = staticData._batches[senderNumber];\n"
    "const elapsed = now - batch.startTime;\n"
    "const batchReady = elapsed >= windowMs;\n"
    "\n"
    "const allMessagesText = batch.messages\n"
    "  .map((m, i) => `${i + 1}. [${m.time}] ${m.text}`)\n"
    "  .join('\\n');\n"
    "\n"
    "return [{\n"
    "  json: {\n"
    "    _skip: false,\n"
    "    senderNumber,\n"
    "    senderName: batch.senderName,\n"
    "    messages: batch.messages,\n"
    "    messageCount: batch.messages.length,\n"
    "    batchReady,\n"
    "    allMessagesText\n"
    "  }\n"
    "}];"
)

# ── Parse AI Output (exact match with workflow.json) ──
parse_ai_output_js = (
    "const aiOutput = $input.first().json?.output || '';\n"
    "let cevap = 'Talebinizi aldık, en kısa sürede döneceğiz.';\n"
    "\n"
    "try {\n"
    "  const jsonMatch = aiOutput.match(/\\{[\\s\\S]*\\}/);\n"
    "  if (jsonMatch) {\n"
    "    const parsed = JSON.parse(jsonMatch[0]);\n"
    "    cevap = parsed.cevap || cevap;\n"
    "  }\n"
    "} catch (e) {}\n"
    "\n"
    "const storeContext = $node[\"Store Context\"].json;\n"
    "const senderName = storeContext.senderName || '';\n"
    "const senderNumber = storeContext.senderNumber || '';\n"
    "const allMessagesText = storeContext.allMessagesText || '';\n"
    "\n"
    "const bildirim = `🔔 YENİ TALEP - filtreto.com\n"
    "👤 Müşteri: ${senderName} (${senderNumber})\n"
    "💬 Gelen Mesajlar:\n"
    "${allMessagesText}\n"
    "\n"
    "🤖 Asistanın Cevabı:\n"
    "${cevap}`;\n"
    "\n"
    "return [{\n"
    "  json: {\n"
    "    bildirim,\n"
    "    cevap\n"
    "  }\n"
    "}];"
)

# ── Stale Batch Check (with manual mode filter) ──
stale_batch_check_js = r"""const staticData = $getWorkflowStaticData('global');
const now = Date.now();
const windowMs = 3 * 60 * 1000;

if (!staticData._batches) staticData._batches = {};
if (!staticData._manualModes) staticData._manualModes = {};

const results = [];

for (const [number, batch] of Object.entries(staticData._batches)) {
  // If customer is in manual mode, discard batch and skip
  if (staticData._manualModes[number] === true) {
    delete staticData._batches[number];
    continue;
  }

  const elapsed = now - batch.startTime;
  if (elapsed >= windowMs && batch.messages.length > 0) {
    results.push({
      json: {
        senderNumber: number,
        senderName: batch.senderName,
        messages: batch.messages,
        messageCount: batch.messages.length,
        allMessagesText: batch.messages
          .map((m, i) => `${i + 1}. [${m.time}] ${m.text}`)
          .join('\n')
      }
    });
  }
}

if (results.length === 0) {
  return [{ json: { senderNumber: '', senderName: '', messageCount: 0, allMessagesText: '', messages: [] } }];
}

return results;"""

# ── Store Context (exact match with workflow.json) ──
store_context_js = (
    "const input = $input.first().json;\n"
    "return [{\n"
    "  json: {\n"
    "    senderNumber: input.senderNumber,\n"
    "    senderName: input.senderName,\n"
    "    allMessagesText: input.allMessagesText,\n"
    "    _prompt: `Gönderen: ${input.senderName} (${input.senderNumber})\\n"
    "Mesaj sayısı: ${input.messageCount}\\n\\n"
    "Mesajlar:\\n${input.allMessagesText}`\n"
    "  }\n"
    "}];"
)

# ── Clear Batch ──
clear_batch_js = r"""const input = $input.first().json;
const staticData = $getWorkflowStaticData('global');

if (staticData._batches && input.senderNumber) {
  delete staticData._batches[input.senderNumber];
}

return [{ json: input }];"""

# ── AI Agent system message (concise, FiltreOto brands, no emojis) ──
ai_agent_system_message = "Sen filtreto.com WhatsApp asistanisin. FiltreOto; Ankara merkezli, orijinal MANN-Filter, FILTRON, FILTORQ, UFI FILTRE, Bosch, Wunder ve Sampiyon gibi markalarin yag, hava, yakit ve polen filtrelerinin/setlerinin satisini yapan kurumsal bir e-ticaret platformudur. Musterilere orijinal urun garantisi, hizli kargo ve sase numarasi ile uyumluluk kontrolu sunar. Kisa ve oz yazarsin.\n\nSADECE su JSON'u dondur, baska bir sey yazma:\n{\"bildirim\":\"KISA bildirim\",\"cevap\":\"KISA cevap\"}\n\nbildirim formati (MUTLAKA bu formatta, tek blok, emoji kullanma):\n[isim] [numara] - [mesajin ozeti 5-10 kelime]\n\ncevap formati:\n- Sadece 1-2 cumle, maksimum 30 kelime\n- Selam verme, direkt konuya gir\n- Turkce\n\nOrnekler:\n1. Musteri arac bilgisi gondermediyse:\n{\"bildirim\":\"Ismail 905331112233 - Yag filtresi siparisi istiyor, arac bilgisi soruldu\",\"cevap\":\"Merhaba, filtre uyumu icin aracinizin marka/model/yil/sase bilgisini paylasir misiniz?\"}\n\n2. Musteri arac bilgisi gonderdiyse:\n{\"bildirim\":\"Ismail 905331112233 - Yag filtresi icin arac bilgilerini gonderdi, ekibe iletildi\",\"cevap\":\"Bilgilerinizi aldik, uzman ekibimiz MANN, Filtron ve Filtorq gibi orijinal markalar arasindan uyumlulugu kontrol edip en kisa surede fiyat ve stok bilgisiyle donecektir.\"}"

# ── Node definitions ──
nodes = [
    {
        "parameters": {
            "httpMethod": "POST",
            "path": "evolution-webhook",
            "responseMode": "responseNode",
            "options": {}
        },
        "id": get_node_id("Webhook1"),
        "name": "Webhook1",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1.1,
        "position": [240, 640],
        "webhookId": "b543e85d-b182-4ddd-af94-3f124a6c2c82"
    },
    {
        "parameters": {
            "respondWith": "json",
            "responseBody": "={\n  \"status\": \"ok\"\n}",
            "options": {}
        },
        "id": get_node_id("Respond OK1"),
        "name": "Respond OK1",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1,
        "position": [240, 432]
    },
    {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 1
                },
                "conditions": [
                    {
                        "id": "cond-allow",
                        "leftValue": "={{ !$json.body.data.key.fromMe || ['++', '--'].includes($json.body.data.message?.conversation || $json.body.data.message?.extendedTextMessage?.text) }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "equals"
                        }
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": get_node_id("fromMe Check"),
        "name": "fromMe Check",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [528, 640]
    },
    {
        "parameters": {
            "jsCode": batch_collector_js
        },
        "id": get_node_id("Batch Collector"),
        "name": "Batch Collector",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [768, 640]
    },
    {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 1
                },
                "conditions": [
                    {
                        "id": "cond-ready",
                        "leftValue": "={{ $json.batchReady }}",
                        "rightValue": True,
                        "operator": {
                            "type": "boolean",
                            "operation": "equals"
                        }
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": get_node_id("Batch Ready?"),
        "name": "Batch Ready?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [1008, 640]
    },
    {
        "parameters": {
            "jsCode": store_context_js
        },
        "id": get_node_id("Store Context"),
        "name": "Store Context",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1248, 640]
    },
    {
        "parameters": {
            "jsCode": parse_ai_output_js
        },
        "id": get_node_id("Parse AI Output"),
        "name": "Parse AI Output",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1808, 624]
    },
    {
        "parameters": {
            "jsCode": clear_batch_js
        },
        "id": get_node_id("Clear Batch"),
        "name": "Clear Batch",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2032, 640]
    },
    {
        "parameters": {
            "options": {
                "systemMessage": ai_agent_system_message
            },
            "promptType": "define",
            "text": "={{ $json._prompt }}"
        },
        "type": "@n8n/n8n-nodes-langchain.agent",
        "typeVersion": 3.1,
        "position": [1472, 624],
        "id": get_node_id("AI Agent"),
        "name": "AI Agent"
    },
    {
        "parameters": {
            "model": {
                "__rl": True,
                "value": "gpt-4o-mini",
                "mode": "list",
                "cachedResultName": "gpt-4o-mini"
            },
            "builtInTools": {},
            "options": {}
        },
        "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        "typeVersion": 1.3,
        "position": [1392, 864],
        "id": get_node_id("OpenAI Chat Model1"),
        "name": "OpenAI Chat Model1",
        "credentials": {
            "openAiApi": {
                "id": "3M52tD49lJ35vXdO",
                "name": "OpenAi account"
            }
        }
    },
    {
        "parameters": {
            "sessionIdType": "customKey",
            "sessionKey": "={{ $json.senderNumber }}"
        },
        "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
        "typeVersion": 1.3,
        "position": [1552, 864],
        "id": get_node_id("Simple Memory"),
        "name": "Simple Memory"
    },
    {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 1
                },
                "conditions": [
                    {
                        "id": "cond-cmd",
                        "leftValue": "={{ $json.command }}",
                        "operator": {
                            "type": "string",
                            "operation": "isNotEmpty"
                        }
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": get_node_id("Command Check"),
        "name": "Command Check",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [1240, 860]
    },
    {
        "parameters": {
            "method": "POST",
            "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "apikey",
                        "value": "089311B617B8-48CF-8BD6-29759A57FDBF"
                    },
                    {
                        "name": "Content-Type",
                        "value": "application/json"
                    }
                ]
            },
            "sendBody": True,
            "contentType": "raw",
            "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905052237182', text: $json.bildirim }) }}",
            "options": {
                "timeout": 30000
            }
        },
        "id": get_node_id("Phone A Send"),
        "name": "Phone A Send",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2288, 416]
    },
    {
        "parameters": {
            "method": "POST",
            "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "apikey",
                        "value": "089311B617B8-48CF-8BD6-29759A57FDBF"
                    },
                    {
                        "name": "Content-Type",
                        "value": "application/json"
                    }
                ]
            },
            "sendBody": True,
            "contentType": "raw",
            "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: '905306056066', text: $json.bildirim }) }}",
            "options": {
                "timeout": 30000
            }
        },
        "id": get_node_id("Phone B Send"),
        "name": "Phone B Send",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2288, 640]
    },
    {
        "parameters": {
            "method": "POST",
            "url": "https://evo.filtreoto.online/message/sendText/filtr",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "apikey",
                        "value": "089311B617B8-48CF-8BD6-29759A57FDBF"
                    },
                    {
                        "name": "Content-Type",
                        "value": "application/json"
                    }
                ]
            },
            "sendBody": True,
            "contentType": "raw",
            "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ number: $json.senderNumber, text: $json.cevap }) }}",
            "options": {
                "timeout": 30000
            }
        },
        "id": get_node_id("Reply to Customer"),
        "name": "Reply to Customer",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2288, 864]
    },
    {
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "seconds",
                        "secondsInterval": 60
                    }
                ]
            }
        },
        "id": get_node_id("Schedule Trigger"),
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [240, 1104]
    },
    {
        "parameters": {
            "jsCode": stale_batch_check_js
        },
        "id": get_node_id("Stale Batch Check"),
        "name": "Stale Batch Check",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [528, 1104]
    },
    {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 1
                },
                "conditions": [
                    {
                        "id": "cond-stale",
                        "leftValue": "={{ $json.messageCount }}",
                        "rightValue": 0,
                        "operator": {
                            "type": "number",
                            "operation": "gt"
                        }
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": get_node_id("Stale Exists?"),
        "name": "Stale Exists?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [768, 1104]
    },
]

# ── Connections ──
connections = {
    "Webhook1": {
        "main": [
            [
                {"node": "Respond OK1", "type": "main", "index": 0},
                {"node": "fromMe Check", "type": "main", "index": 0},
            ]
        ]
    },
    "fromMe Check": {
        "main": [
            [{"node": "Batch Collector", "type": "main", "index": 0}],
            [],
        ]
    },
    "Batch Collector": {
        "main": [
            [{"node": "Batch Ready?", "type": "main", "index": 0}]
        ]
    },
    "Batch Ready?": {
        "main": [
            [{"node": "Store Context", "type": "main", "index": 0}],
            [{"node": "Command Check", "type": "main", "index": 0}],
        ]
    },
    "Store Context": {
        "main": [
            [{"node": "AI Agent", "type": "main", "index": 0}]
        ]
    },
    "AI Agent": {
        "main": [
            [{"node": "Parse AI Output", "type": "main", "index": 0}]
        ]
    },
    "Parse AI Output": {
        "main": [
            [{"node": "Clear Batch", "type": "main", "index": 0}]
        ]
    },
    "Clear Batch": {
        "main": [
            [
                {"node": "Phone A Send", "type": "main", "index": 0},
                {"node": "Phone B Send", "type": "main", "index": 0},
                {"node": "Reply to Customer", "type": "main", "index": 0},
            ]
        ]
    },
    "Schedule Trigger": {
        "main": [
            [{"node": "Stale Batch Check", "type": "main", "index": 0}]
        ]
    },
    "Stale Batch Check": {
        "main": [
            [{"node": "Stale Exists?", "type": "main", "index": 0}]
        ]
    },
    "Stale Exists?": {
        "main": [
            [{"node": "Store Context", "type": "main", "index": 0}],
            [],
        ]
    },
    "OpenAI Chat Model1": {
        "ai_languageModel": [
            [{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]
        ]
    },
    "Simple Memory": {
        "ai_memory": [
            [{"node": "AI Agent", "type": "ai_memory", "index": 0}]
        ]
    },
    "Command Check": {
        "main": [
            [{"node": "Phone A Send", "type": "main", "index": 0}],
            [],
        ]
    },
}

# ── Build workflow.json ──
with open("workflow.json", "r", encoding="utf-8") as f:
    wf = json.load(f)

wf["nodes"] = nodes
wf["connections"] = connections
wf["settings"] = {
    "executionOrder": "v1",
    "binaryMode": "separate",
    "availableInMCP": False,
    "callerPolicy": "workflowsFromSameOwner",
    "timeSavedMode": "fixed",
    "saveDataSuccessExecution": "all",
    "saveExecutionProgress": True,
    "saveManualExecutions": True,
}
wf["staticData"] = {
    "node:Schedule Trigger": {"recurrenceRules": []},
    "global": {"_batches": {}},
}
wf["meta"] = {"templateCredsSetupCompleted": True}
wf["pinData"] = {}

with open("workflow.json", "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)

print("workflow.json successfully updated locally.")
print(f"Nodes: {len(nodes)}")
print(f"Connections: {sum(len(v['main'][0]) for v in connections.values() if v.get('main', [[]])[0])}")
