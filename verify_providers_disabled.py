#!/usr/bin/env python3
"""
Verify all direct providers are DISABLED at the end
"""
import requests
import json

BASE_URL = "https://b56603c6-4e16-41ee-a1f9-a01a1c612d5a.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@aiplatform.com"
ADMIN_PASSWORD = "admin12345"

def login():
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    return resp.json().get("token")

def main():
    print("Verifying all direct providers are DISABLED...")
    token = login()
    
    resp = requests.get(f"{BASE_URL}/admin/providers",
                       headers={"Authorization": f"Bearer {token}"})
    
    providers = resp.json()
    
    print(f"\nFound {len(providers)} providers:")
    
    enabled_count = 0
    for p in providers:
        slug = p.get("slug")
        enabled = p.get("enabled", False)
        has_key = p.get("has_key", False)
        
        status = "🟢 ENABLED" if enabled else "⚪ DISABLED"
        key_status = "🔑 HAS KEY" if has_key else "❌ NO KEY"
        
        print(f"  {status} {key_status} - {slug}")
        
        if enabled:
            enabled_count += 1
    
    print(f"\n{'✅' if enabled_count == 0 else '⚠️'} {enabled_count} provider(s) enabled")
    
    if enabled_count > 0:
        print("\n⚠️  WARNING: Some providers are enabled. Disabling them now...")
        
        for p in providers:
            if p.get("enabled"):
                pid = p.get("id")
                slug = p.get("slug")
                print(f"  Disabling {slug}...")
                
                resp = requests.put(f"{BASE_URL}/admin/providers/{pid}",
                                   json={"enabled": False},
                                   headers={"Authorization": f"Bearer {token}"})
                
                if resp.status_code == 200:
                    print(f"    ✅ Disabled {slug}")
                else:
                    print(f"    ❌ Failed to disable {slug}: {resp.status_code}")
        
        print("\n✅ All providers disabled")
    else:
        print("\n✅ All providers already disabled (correct)")

if __name__ == "__main__":
    main()
