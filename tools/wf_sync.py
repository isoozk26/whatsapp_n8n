#!/usr/bin/env python3
"""Tool 5: Git Sync - commit ve push islemlerini otomatik yapar"""
import subprocess
import sys
import datetime
import shlex

SENSITIVE_PATTERNS = ['.env', 'credentials', 'secrets', '.pem', '.key', '.p12']

def run(cmd, shell=False):
    if isinstance(cmd, str) and not shell:
        cmd = shlex.split(cmd)
    r = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def check_staged_for_secrets():
    stdout, _, _ = run("git diff --cached --name-only")
    if not stdout:
        return []
    flagged = []
    for f in stdout.split('\n'):
        f_lower = f.lower()
        for pattern in SENSITIVE_PATTERNS:
            if pattern in f_lower:
                flagged.append(f)
                break
    return flagged

def sync(message=None, push=True):
    print(f"\n{'='*50}")
    print("GIT SYNC - Gitea Senkronizasyon")
    print(f"{'='*50}")

    # Status kontrol
    print("\n  [1] Degisiklikler kontrol ediliyor...")
    stdout, stderr, code = run("git status --short")
    if not stdout:
        print("  [OK] Degisiklik yok, islem gerekmiyor.")
        return True

    lines = stdout.strip().split("\n")
    print(f"  {len(lines)} dosya degisti:")
    for line in lines[:10]:
        print(f"    {line}")
    if len(lines) > 10:
        print(f"    ... ve {len(lines)-10} dosya daha")

    # Diff ozeti
    print("\n  [2] Diff ozeti:")
    stdout, _, _ = run("git diff --stat")
    if stdout:
        for line in stdout.strip().split("\n")[:5]:
            print(f"    {line}")

    # Commit mesaji
    if not message:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        message = f"Auto update: {now}"

    print(f"\n  [3] Commit: '{message}'")

    # Add all changes (respects .gitignore)
    run("git add -A")

    # Check for sensitive files before committing
    flagged = check_staged_for_secrets()
    if flagged:
        print(f"  [UYARI] Hassas dosyalar staged edildi:")
        for f in flagged:
            print(f"    - {f}")
        print("  Commit iptal edildi. .gitignore'a ekleyin veya manuel onay verin.")
        return False

    # Commit - use list form to avoid shell injection
    stdout, stderr, code = run(["git", "commit", "-m", message])
    if code != 0:
        print(f"  [HATA] Commit basarisiz: {stderr}")
        return False
    print(f"  [OK] {stdout}")

    # Push
    if not push:
        print("\n  [4] Push atlandi (--no-push)")
        print(f"\n  SYNC TAMAMLANDI (push yok)")
        print(f"{'='*50}\n")
        return True

    print("\n  [4] Push yapiliyor...")
    stdout, stderr, code = run("git push")
    if code != 0:
        print(f"  [HATA] Push basarisiz: {stderr}")
        return False
    print(f"  [OK] {stdout}")

    print(f"\n  SYNC TAMAMLANDI")
    print(f"{'='*50}\n")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Git sync tool")
    parser.add_argument("message", nargs="*", help="Commit message")
    parser.add_argument("--no-push", action="store_true", help="Skip push")
    args = parser.parse_args()
    msg = " ".join(args.message) if args.message else None
    ok = sync(msg, push=not args.no_push)
    sys.exit(0 if ok else 1)
