import json
import uuid

# We reuse original IDs where appropriate to keep settings and layout clean
node_ids = {
    "Webhook1": "65f757d5-7045-45df-90aa-a959a4a10519",
    "Respond OK1": "c370ae94-67de-411e-8368-4d479f00e421",
    "fromMe Check": "5527d4b8-019e-4bb6-bbd3-526fab1f9470", # reused Başkasından mı geldi?1 ID
    "AI Agent": "f822155a-6d0b-444d-af11-56313d6256e9",
    "OpenAI Chat Model": "62b80dfa-375f-4a90-a673-4c6bf70111be",
    "Window Buffer Memory": "0f2b18fc-83e1-4ed4-9a55-6f4e2b31de41",
    "Phone A Send": "61d75176-a426-41d9-8a8e-6d4c626f8df5", # reused Telefon A'ya Gönder1 ID
    "Phone B Send": "e43d47e9-69fe-4bbd-9e59-59ccd0a31629", # reused Telefon B'ye Gönder1 ID
}

# Helper to generate stable or random UUIDs for new nodes
def get_node_id(name):
    if name in node_ids:
        return node_ids[name]
    # generate a stable uuid based on name to make deployment reproducible
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"n8n.workflow.filtreoto.{name}"))

# 1. Batch Collector JS Code
batch_collector_js = """const staticData = $getWorkflowStaticData('global');
const input = $input.first().json;

const rawJid = input.body.data.key.remoteJid || '';
const senderNumber = rawJid.replace('@s.whatsapp.net', '').replace('@g.us', '');
const senderName = input.body.data.pushName || senderNumber;
const messageText = input.body.data.message?.conversation
  || input.body.data.message?.extendedTextMessage?.text
  || '[Medya Mesajı]';

const now = Date.now();
const windowMs = 3 * 60 * 1000;

if (!staticData._batches) staticData._batches = {};

if (!staticData._batches[senderNumber]) {
  staticData._batches[senderNumber] = {
    messages: [],
    startTime: now,
    senderName: senderName
  };
}

staticData._batches[senderNumber].messages.push({
  text: messageText,
  time: new Date(now).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
});

staticData._batches[senderNumber].senderName = senderName;

const batch = staticData._batches[senderNumber];
const elapsed = now - batch.startTime;
const batchReady = elapsed >= windowMs;

const allMessagesText = batch.messages
  .map((m, i) => `${i + 1}. [${m.time}] ${m.text}`)
  .join('\\n');

return [{
  json: {
    senderNumber,
    senderName: batch.senderName,
    messages: batch.messages,
    messageCount: batch.messages.length,
    batchReady,
    allMessagesText
  }
}];"""

# 2. Parse AI Output JS Code
parse_ai_output_js = """const aiOutput = $input.first().json?.output || '';
let senderNumber = '';
let senderName = '';

try {
  const storeContext = $('Store Context').item.json;
  senderNumber = storeContext.senderNumber || '';
  senderName = storeContext.senderName || '';
} catch (e) {
  // fallback
}

let bildirim = '';
let cevap = 'Mesajınız alınmıştır, en kısa sürede size dönüş yapılacaktır.';

try {
  const jsonMatch = aiOutput.match(/\\{[\\s\\S]*\\}/);
  if (jsonMatch) {
    const parsed = JSON.parse(jsonMatch[0]);
    bildirim = parsed.bildirim || aiOutput;
    cevap = parsed.cevap || cevap;
    if (parsed.gonderenNumara) senderNumber = parsed.gonderenNumara;
    if (parsed.gonderenAd) senderName = parsed.gonderenAd;
  } else {
    bildirim = aiOutput;
  }
} catch (e) {
  bildirim = aiOutput;
}

return [{
  json: {
    bildirim,
    cevap,
    senderNumber,
    senderName
  }
}];"""

# 3. Stale Batch Check JS Code
stale_batch_check_js = """const staticData = $getWorkflowStaticData('global');
const now = Date.now();
const windowMs = 3 * 60 * 1000;

if (!staticData._batches) staticData._batches = {};

const results = [];

for (const [number, batch] of Object.entries(staticData._batches)) {
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
          .join('\\n')
      }
    });
  }
}

if (results.length === 0) {
  return [{ json: { senderNumber: '', senderName: '', messageCount: 0, allMessagesText: '', messages: [] } }];
}

return results;"""

# Nodes schema definition
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
        "position": [240, 420]
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
                        "id": "cond-fromMe",
                        "leftValue": "={{ $json.body.data.key.fromMe }}",
                        "rightValue": False,
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
        "position": [520, 640]
    },
    {
        "parameters": {
            "jsCode": batch_collector_js
        },
        "id": get_node_id("Batch Collector"),
        "name": "Batch Collector",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [760, 640]
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
        "position": [1000, 640]
    },
    {
        "parameters": {
            "jsCode": "const input = $input.first().json;\nreturn [{\n  json: {\n    senderNumber: input.senderNumber,\n    senderName: input.senderName,\n    _prompt: `GÖNDEREN BİLGİLERİ:\\nİsim: ${input.senderName}\\nNumara: ${input.senderNumber}\\n\\nMESAJLAR (${input.messageCount} adet):\\n${input.allMessagesText}`\n  }\n}];"
        },
        "id": get_node_id("Store Context"),
        "name": "Store Context",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1240, 640]
    },
    {
        "parameters": {
            "options": {
                "systemMessage": "Sen filtreto.com müşteri hizmetleri asistanısın.\n\nGörev: Gelen WhatsApp mesajlarını analiz et ve SADECE aşağıdaki JSON formatında yanıt ver. Başka hiçbir metin ekleme.\n\nJSON Formatı:\n{\"gonderenNumara\":\"numarayı buraya aynen yaz\",\"gonderenAd\":\"ismi buraya aynen yaz\",\"bildirim\":\"bildirim metni\",\"cevap\":\"cevap metni\"}\n\nBİLDİRİM Kuralları:\n- 🔔 YENİ MESAJ — filtreto.com ile başla\n- 👤 Gönderen ismini yaz\n- 📞 Numarayı yaz\n- 💬 Mesajları detaylı özetle, müşterinin ne istediğini analiz et\n- 📝 AI Notu: Kısa analiz + önerilen aksiyon\n\nCEVAP Kuralları:\n- Kısa, profesyonel ve yardımcı ol\n- Müşterinin sorusuna doğrudan cevap ver\n- filtreto.com ürün/hizmetleriyle ilgili yardımcı ol\n- Gerekirse ek bilgi iste\n- Türkçe yaz\n\nÖNEMLİ: gonderenNumara ve gonderenAd değerlerini mesajdaki bilgilerden AYNEN kopyala. SADECE JSON döndür."
            },
            "promptType": "define",
            "text": "={{ $json._prompt }}"
        },
        "id": get_node_id("AI Agent"),
        "name": "AI Agent",
        "type": "@n8n/n8n-nodes-langchain.agent",
        "typeVersion": 1.7,
        "position": [1520, 640]
    },
    {
        "parameters": {
            "model": "gpt-4o-mini",
            "options": {
                "temperature": 0.3
            }
        },
        "id": get_node_id("OpenAI Chat Model"),
        "name": "OpenAI Chat Model",
        "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        "typeVersion": 1.2,
        "position": [1420, 860]
    },
    {
        "parameters": {
            "sessionIdType": "customKey",
            "sessionKey": "={{ $json.senderNumber }}",
            "contextWindowLength": 20
        },
        "id": get_node_id("Window Buffer Memory"),
        "name": "Window Buffer Memory",
        "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
        "typeVersion": 1.3,
        "position": [1620, 860]
    },
    {
        "parameters": {
            "jsCode": parse_ai_output_js
        },
        "id": get_node_id("Parse AI Output"),
        "name": "Parse AI Output",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1780, 640]
    },
    {
        "parameters": {
            "jsCode": "const input = $input.first().json;\nconst staticData = $getWorkflowStaticData('global');\n\nif (staticData._batches && input.senderNumber) {\n  delete staticData._batches[input.senderNumber];\n}\n\nreturn [{ json: input }];"
        },
        "id": get_node_id("Clear Batch"),
        "name": "Clear Batch",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2020, 640]
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
        "position": [2280, 416]
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
        "position": [2280, 640]
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
        "position": [2280, 864]
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
        "position": [240, 1100]
    },
    {
        "parameters": {
            "jsCode": stale_batch_check_js
        },
        "id": get_node_id("Stale Batch Check"),
        "name": "Stale Batch Check",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [520, 1100]
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
        "position": [760, 1100]
    }
]

connections = {
    "Webhook1": {
        "main": [
            [
                {
                    "node": "Respond OK1",
                    "type": "main",
                    "index": 0
                },
                {
                    "node": "fromMe Check",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    },
    "fromMe Check": {
        "main": [
            [
                {
                    "node": "Batch Collector",
                    "type": "main",
                    "index": 0
                }
            ],
            []
        ]
    },
    "Batch Collector": {
        "main": [
            [
                {
                    "node": "Batch Ready?",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    },
    "Batch Ready?": {
        "main": [
            [
                {
                    "node": "Store Context",
                    "type": "main",
                    "index": 0
                }
            ],
            []
        ]
    },
    "Store Context": {
        "main": [
            [
                {
                    "node": "AI Agent",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    },
    "AI Agent": {
        "main": [
            [
                {
                    "node": "Parse AI Output",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    },
    "Parse AI Output": {
        "main": [
            [
                {
                    "node": "Clear Batch",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    },
    "Clear Batch": {
        "main": [
            [
                {
                    "node": "Phone A Send",
                    "type": "main",
                    "index": 0
                },
                {
                    "node": "Phone B Send",
                    "type": "main",
                    "index": 0
                },
                {
                    "node": "Reply to Customer",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    },
    "Schedule Trigger": {
        "main": [
            [
                {
                    "node": "Stale Batch Check",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    },
    "Stale Batch Check": {
        "main": [
            [
                {
                    "node": "Stale Exists?",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    },
    "Stale Exists?": {
        "main": [
            [
                {
                    "node": "Store Context",
                    "type": "main",
                    "index": 0
                }
            ],
            []
        ]
    },
    "OpenAI Chat Model": {
        "ai_languageModel": [
            [
                {
                    "node": "AI Agent",
                    "type": "ai_languageModel",
                    "index": 0
                }
            ]
        ]
    },
    "Window Buffer Memory": {
        "ai_memory": [
            [
                {
                    "node": "AI Agent",
                    "type": "ai_memory",
                    "index": 0
                }
            ]
        ]
    }
}

# Read base workflow.json to preserve general settings/ID/Name
with open("workflow.json", "r", encoding="utf-8") as f:
    wf_base = json.load(f)

# Update fields
wf_base["name"] = "WhatsApp AI Bildirim - 3dk Batch"
wf_base["nodes"] = nodes
wf_base["connections"] = connections

with open("workflow.json", "w", encoding="utf-8") as f:
    json.dump(wf_base, f, indent=2, ensure_ascii=False)

print("workflow.json successfully updated locally.")
