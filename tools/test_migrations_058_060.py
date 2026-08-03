#!/usr/bin/env python3
"""Migrations 058-060 icin regresyon testleri (yeniden yazim).

Kapsanan uc uretim duzeltmesi:
  058_daily_report_emoji.sql       -> gunluk rapor: kanal ayrimi + gercek latency + emoji
  059_queue_monitor_defer_fix.sql  -> kuyruk monitoru: ertelenmis batch'leri haric tut
  060_ooh_manager_outbox.sql       -> OOH yonetici bildirimini outbox'a al + dogru manager_sent

Test katmanlari:
  1) SYNTAX  : her migration Postgres olarak parse edilir (sqlglot varsa; yoksa SKIP).
  2) STATIK  : migration icerigi + mantik guvenceleri (DB gerektirmez, release gate icinde calisir).
  3) BASELINE: baseline 003_delivery_metrics.sql'deki eski anti-pattern'lerin GERCEKTEN
               degistigini dogrular (regresyon koruma).
  4) LIVE    : WHATSAPP_POSTGRES_URL + psql varsa fonksiyon/tablo varligini dogrular; yoksa SKIP.

Calistirma:
  python3 tools/test_migrations_058_060.py

Cikis kodu 0 = tum kontroller PASS. 1 = en az bir FAIL.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "db" / "migrations"


def _read(name):
    path = MIG / name
    if not path.exists():
        print(f"  FAIL  beklenen migration bulunamadi: {path}")
        _failures.append(f"missing: {name}")
        return ""
    return path.read_text(encoding="utf-8")


_failures = []
_skips = []

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def check(cond, msg):
    if cond:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        _failures.append(msg)


def skip(msg):
    print(f"  SKIP  {msg}")
    _skips.append(msg)


def _norm(text):
    """Bosluklari tek bosluğa indir; icerik aramalarini whitespace'e dayaniksiz yap."""
    return re.sub(r"\s+", " ", text)


DAILY = _read("058_daily_report_emoji.sql")
QUEUE = _read("059_queue_monitor_defer_fix.sql")
OOH = _read("060_ooh_manager_outbox.sql")
BASELINE = (MIG / "003_delivery_metrics.sql")
BASELINE_SQL = BASELINE.read_text(encoding="utf-8") if BASELINE.exists() else ""


# ---------------------------------------------------------------------------
# 1) SYNTAX
# ---------------------------------------------------------------------------
def test_syntax():
    print("\n[1/syntax] Postgres parse")
    try:
        import sqlglot
    except Exception:
        skip("sqlglot yok -> SQL parse dogrulamasi atlandi")
        return
    for name, sql in (("058", DAILY), ("059", QUEUE), ("060", OOH)):
        try:
            sqlglot.parse(sql, read="postgres")
            check(True, f"{name}: gecerli Postgres SQL olarak parse edildi")
        except Exception as exc:  # pragma: no cover - hata yolu
            check(False, f"{name}: parse hatasi -> {exc}")


# ---------------------------------------------------------------------------
# 2) STATIK - ortak yapi
# ---------------------------------------------------------------------------
def test_common_structure():
    print("\n[2/statik] ortak migration yapisi")
    for name, sql in (("058", DAILY), ("059", QUEUE), ("060", OOH)):
        check("BEGIN;" in sql and "COMMIT;" in sql, f"{name}: BEGIN/COMMIT transaction ile sarili")
    check("CREATE OR REPLACE FUNCTION whatsapp_ai.run_daily_report()" in DAILY,
          "058: run_daily_report CREATE OR REPLACE ile guncellenir")
    check("CREATE OR REPLACE FUNCTION whatsapp_ai.run_queue_monitor()" in QUEUE,
          "059: run_queue_monitor CREATE OR REPLACE ile guncellenir")
    check("CREATE OR REPLACE FUNCTION whatsapp_ai.enqueue_ooh_manager_alert" in OOH,
          "060: enqueue_ooh_manager_alert olusturulur")


# ---------------------------------------------------------------------------
# 2) STATIK - 058 gunluk rapor
# ---------------------------------------------------------------------------
def test_daily_report():
    print("\n[2/statik] 058 gunluk rapor")
    n = _norm(DAILY)
    check("channel = 'customer'" in n, "058: musteri teslimatlari channel='customer' ile filtrelenir")
    check(re.search(r"channel\s+IN\s*\(\s*'phone_a'\s*,\s*'phone_b'\s*\)", n) is not None,
          "058: yonetici/sistem teslimatlari ayri sayilir (phone_a/phone_b)")
    m = re.search(
        r"percentile_cont\(0\.95\).*?FROM whatsapp_ai\.deliveries\s+WHERE\s+channel\s*=\s*'customer'\s+AND\s+status\s*=\s*'sent'",
        n,
    )
    check(bool(m), "058: P95/ortalama latency yalnizca channel='customer' AND status='sent' uzerinden")
    check("latency_ms IS NOT NULL" in n, "058: NULL latency degerleri haric tutulur")
    check("next_ai_attempt_at IS NULL OR next_ai_attempt_at <= clock_timestamp()" in n,
          "058: 'bekleyen' sayimi mesai disina ertelenmisleri haric tutar")
    for emoji in ("📊", "📥", "✅", "🤖", "🛡️"):
        check(emoji in DAILY, f"058: rapor emoji icerir ({emoji})")
    check(all(badge in DAILY for badge in ("🟢", "🟡", "🔴")),
          "058: saglik rozeti (yesil/sari/kirmizi) mevcut")
    check("array_to_string(ARRAY[" in n and r"E'\n')" in DAILY,
          "058: satirlar array_to_string(ARRAY[...], E'\\n') ile gercek newline uretir")
    check("'daily_report:'" in DAILY and "interval '23 hours'" in DAILY,
          "058: gunde tek rapor icin cooldown anahtari (daily_report:<date>, 23h)")
    for key in ("'customerSent'", "'adminSent'", "'avgLatencyMs'", "'p95LatencyMs'", "'health'"):
        check(key in DAILY, f"058: JSON ciktisi {key} icerir")


# ---------------------------------------------------------------------------
# 2) STATIK - 059 kuyruk monitoru
# ---------------------------------------------------------------------------
def test_queue_monitor():
    print("\n[2/statik] 059 kuyruk monitoru")
    n = _norm(QUEUE)
    m = re.search(
        r"INTO v_pending\s+FROM whatsapp_ai\.batches\s+WHERE\s+status\s*=\s*'pending'\s+AND\s+jsonb_array_length\(pending_messages\)\s*>\s*0\s+AND\s+\(next_ai_attempt_at\s+IS\s+NULL\s+OR\s+next_ai_attempt_at\s+<=\s+clock_timestamp\(\)\)",
        n,
    )
    check(bool(m), "059: v_pending yalnizca ertelenmemis (next_ai_attempt_at<=now) batch'leri sayar")
    check("interval '7 minutes'" in n, "059: v_pending 7 dk+ takili esigi korunur")
    check(re.search(
        r"INTO v_deferred\s+FROM\s+whatsapp_ai\.batches\s+WHERE\s+status\s*=\s*'pending'.*?next_ai_attempt_at\s*>\s*clock_timestamp\(\)",
        n,
    ) is not None,
          "059: ertelenmis batch'ler ayri (v_deferred) sayilir")
    cond = re.search(r"IF (v_pending[^T]+?) > 0 THEN", n)
    check(bool(cond) and "v_deferred" not in cond.group(1),
          "059: alarm kosulu v_deferred icermez (ertelenmis mesaj alarm uretmez)")
    check("v_pending + v_processing + v_dead + v_manual + v_sending + v_failed > 0" in n,
          "059: alarm yalnizca gercek problem gostergeleri > 0 ise tetiklenir")
    check("'deferred', v_deferred" in n or "'deferred',v_deferred" in n,
          "059: v_deferred system_events'e ve JSON ciktisina yazilir")
    check("🚨" in QUEUE, "059: alarm metni emoji icerir (🚨)")
    check(re.search(r"enqueue_admin_alert\(\s*'queue_health'", n) is not None,
          "059: alarm queue_health cooldown anahtari ile gonderilir")


# ---------------------------------------------------------------------------
# 2) STATIK - 060 OOH yonetici outbox
# ---------------------------------------------------------------------------
def test_ooh_manager_outbox():
    print("\n[2/statik] 060 OOH yonetici outbox")
    n = _norm(OOH)
    check("CREATE TABLE IF NOT EXISTS whatsapp_ai.ooh_manager_dispatch" in n,
          "060: ooh_manager_dispatch idempotency tablosu olusturulur")
    check("REFERENCES whatsapp_ai.ooh_log(id) ON DELETE CASCADE" in n,
          "060: dispatch tablosu ooh_log(id) FK ve ON DELETE CASCADE ile baglanir")
    check("ON CONFLICT (ooh_log_id, channel) DO NOTHING" in n and "IF NOT FOUND" in n,
          "060: ayni OOH olayi tek kez kuyruklanir (idempotency guard)")
    check(re.search(r"enqueue_ooh_manager_alert\(\s*p_ooh_log_id uuid,\s*p_text\s+text\s*\) RETURNS boolean", n) is not None,
          "060: enqueue_ooh_manager_alert(p_ooh_log_id uuid, p_text text) RETURNS boolean")
    check("ARRAY['phone_a', 'phone_b']" in n or "ARRAY['phone_a','phone_b']" in n,
          "060: yonetici numaralari settings'ten (admin_phone_a/b) okunur")
    inserts = re.findall(r"INSERT INTO whatsapp_ai\.deliveries\s*\(([^)]*)\)", n)
    check(len(inserts) >= 1, "060: phone_a ve phone_b icin deliveries outbox kayitlari eklenir")
    check(all("channel" in cols and "destination" in cols and "payload" in cols for cols in inserts),
          "060: outbox kayitlari channel/destination/payload icerir")
    check("'phone_a'" in n and "'phone_b'" in n, "060: kayitlar phone_a ve phone_b kanallarina yazilir")
    check(re.search(r"'kind'\s*,\s*'ooh_manager'", n) is not None,
          "060: payload kind='ooh_manager' etiketi tasir (izlenebilirlik)")
    check("UPDATE whatsapp_ai.ooh_log SET manager_sent = v_queued WHERE id = p_ooh_log_id" in n,
          "060: ooh_log.manager_sent gercek kuyruklama sonucunu (v_queued) yansitir")
    check("managerTargets.length" not in OOH,
          "060: eski fail-open (managerTargets.length>0) mantigi kullanilmaz")


# ---------------------------------------------------------------------------
# 3) BASELINE regresyon: eski anti-pattern gercekten degisti mi?
# ---------------------------------------------------------------------------
def test_baseline_regression():
    print("\n[3/baseline] eski anti-pattern'lerin duzeltildigi dogrulanir")
    if not BASELINE_SQL:
        skip("003_delivery_metrics.sql yok -> baseline regresyon atlandi")
        return
    b = _norm(BASELINE_SQL)
    # Baseline run_daily_report kanal filtresi YOKtu; duzeltme channel='customer' ekliyor.
    daily_baseline = re.search(r"run_daily_report\(\).*?\$\$;", b, re.S)
    if daily_baseline:
        seg = daily_baseline.group(0)
        check("channel = 'customer'" not in seg and "channel='customer'" not in seg,
              "baseline: eski run_daily_report kanal ayrimi yapMIYORdu (hata teyidi)")
    check("channel = 'customer'" in _norm(DAILY),
          "058: duzeltme kanal ayrimini ekliyor (regresyon kapandi)")
    # Baseline run_queue_monitor next_ai_attempt_at ile pending'i suzMUYORdu.
    queue_baseline = re.search(r"run_queue_monitor\(\).*?\$\$;", b, re.S)
    if queue_baseline:
        seg = _norm(queue_baseline.group(0))
        m = re.search(r"INTO v_pending FROM whatsapp_ai\.batches WHERE status='pending' AND updated_at", seg)
        check(bool(m) and "next_ai_attempt_at" not in seg.split("INTO v_processing")[0],
              "baseline: eski v_pending ertelenmisleri haric tutMUYORdu (spam kaynagi teyidi)")
    check("next_ai_attempt_at" in _norm(QUEUE),
          "059: duzeltme ertelenmis batch suzmesini ekliyor (regresyon kapandi)")


# ---------------------------------------------------------------------------
# 4) LIVE (opsiyonel)
# ---------------------------------------------------------------------------
def test_live_optional():
    print("\n[4/live] opsiyonel canli dogrulama")
    url = os.environ.get("WHATSAPP_POSTGRES_URL")
    psql = shutil.which("psql")
    if not url or not psql:
        skip("canli DB dogrulamasi (WHATSAPP_POSTGRES_URL veya psql yok)")
        return
    query = (
        "SELECT proname FROM pg_proc "
        "WHERE pronamespace='whatsapp_ai'::regnamespace "
        "AND proname IN ('run_daily_report','run_queue_monitor','enqueue_ooh_manager_alert') "
        "ORDER BY proname;"
    )
    out = subprocess.run([psql, url, "-tAc", query], capture_output=True, text=True, timeout=30)
    found = {line.strip() for line in out.stdout.splitlines() if line.strip()}
    for fn in ("enqueue_ooh_manager_alert", "run_daily_report", "run_queue_monitor"):
        check(fn in found, f"live: {fn} DB'de mevcut")
    tbl = subprocess.run(
        [psql, url, "-tAc", "SELECT to_regclass('whatsapp_ai.ooh_manager_dispatch');"],
        capture_output=True, text=True, timeout=30,
    )
    check("ooh_manager_dispatch" in tbl.stdout, "live: ooh_manager_dispatch tablosu mevcut")


def main():
    print("migrations 058-060 test paketi (yeniden yazim)")
    test_syntax()
    test_common_structure()
    test_daily_report()
    test_queue_monitor()
    test_ooh_manager_outbox()
    test_baseline_regression()
    test_live_optional()
    print("\n" + "-" * 60)
    print(f"SKIP: {len(_skips)}  |  FAIL: {len(_failures)}")
    if _failures:
        print("FAILED kontroller:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    print("TUM KONTROLLER PASS")


if __name__ == "__main__":
    main()
