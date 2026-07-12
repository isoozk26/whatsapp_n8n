#!/usr/bin/env python3
"""Tool 5: Git Sync - commit ve push islemlerini otomatik yapar"""
import subprocess
import sys
import datetime

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def sync(message=None):
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

    # Add + Commit
    run("git add .")
    stdout, stderr, code = run(f'git commit -m "{message}"')
    if code != 0:
        print(f"  [HATA] Commit basarisiz: {stderr}")
        return False
    print(f"  [OK] {stdout}")

    # Push
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
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    ok = sync(msg)
    sys.exit(0 if ok else 1)
