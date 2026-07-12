# WhatsApp n8n Workflow

Üretim artifact'i `workflow.json`, tek kaynak ise `build_workflow.py` dosyasıdır.

## Yerel doğrulama

```powershell
python build_workflow.py
python tools/wf_validate.py workflow.json
python tools/test_workflow_contract.py
```

Build, bütün JavaScript Code node'larını kontrol eder ve ardından workflow'u üretir.
Contract testi HTTP başarı/hata dallarının delivery ledger etiketlerinden geçtiğini
ve webhook yanıt modunun tutarlı olduğunu doğrular. Bu testler ağa bağlanmaz.

## Canlı test ve deploy

`tools/wf_test_webhook.py` gerçek webhook'a mesaj gönderir. Yalnızca kontrollü
bir test penceresinde çalıştırılmalıdır. `upload_to_n8n.py` canlı workflow'u
değiştirir; deploy öncesinde yukarıdaki üç yerel kontrolün tamamı geçmelidir.

Rollback için n8n'deki önceki workflow sürümü veya önceki Git commit'indeki
`workflow.json` yeniden yüklenir.
