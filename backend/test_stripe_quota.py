#!/usr/bin/env python3
"""
Stripe Quota & Reset Test Script
Bu script ile Stripe entegrasyonu ve quota reset mantığını test edebilirsiniz.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Backend dizinini path'e ekle
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Environment variables yükle
from dotenv import load_dotenv
load_dotenv()

# MongoDB ve backend modülleri
from motor.motor_asyncio import AsyncIOMotorClient
import stripe

# Backend fonksiyonlarını import et
from server import (
    get_stripe_lookup_key,
    get_stripe_price_by_lookup_key,
    check_and_reset_quota,
    get_organization_plan,
    get_plan_info
)

# Stripe API key
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# MongoDB bağlantısı
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "royal_koltuk_dev")


async def test_lookup_key_generation():
    """Test 1: Lookup key generation"""
    print("\n" + "="*70)
    print("TEST 1: Lookup Key Generation")
    print("="*70)
    
    test_cases = [
        ('tier_1_standard', 'monthly', 'try'),
        ('tier_1_standard', 'monthly', 'gbp'),
        ('tier_2_profesyonel', 'monthly', 'try'),
        ('tier_2_profesyonel', 'yearly', 'gbp'),
        ('tier_3_premium', 'monthly', 'try'),
    ]
    
    for plan_id, cycle, currency in test_cases:
        key = get_stripe_lookup_key(plan_id, cycle, currency)
        print(f"✅ {plan_id:25} | {cycle:8} | {currency:4} → '{key}'")
    
    print("\n✅ Lookup key generation test passed!")


async def test_stripe_price_lookup():
    """Test 2: Stripe Price lookup"""
    print("\n" + "="*70)
    print("TEST 2: Stripe Price Lookup")
    print("="*70)
    
    if not STRIPE_SECRET_KEY:
        print("⚠️  STRIPE_SECRET_KEY tanımlı değil, test atlanıyor")
        return
    
    # Not: Stripe'da "standart" kullanılıyor (Türkçe), "standard" değil
    test_keys = [
        'standart_monthly_try',
        'standart_monthly_gbp',
        'professional_monthly_try',
        'professional_monthly_gbp',
    ]
    
    for lookup_key in test_keys:
        try:
            price = get_stripe_price_by_lookup_key(lookup_key)
            if price:
                print(f"✅ '{lookup_key}': Found - ID: {price.id}, Currency: {price.currency.upper()}, Amount: {price.unit_amount/100}")
            else:
                print(f"❌ '{lookup_key}': Not found in Stripe")
        except Exception as e:
            print(f"❌ '{lookup_key}': Error - {e}")
    
    print("\n✅ Stripe price lookup test completed!")


async def test_quota_reset_logic():
    """Test 3: Quota reset logic"""
    print("\n" + "="*70)
    print("TEST 3: Quota Reset Logic")
    print("="*70)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Test organization bul veya oluştur
    test_org_id = "test_quota_reset_org"
    
    # Test case 1: Ay değişmiş (reset gerekli)
    print("\n📋 Test Case 1: Ay değişmiş (reset gerekli)")
    last_month = datetime.now(timezone.utc) - timedelta(days=35)
    
    await db.organization_plans.update_one(
        {"organization_id": test_org_id},
        {
            "$set": {
                "organization_id": test_org_id,
                "plan_id": "tier_1_standard",
                "quota_usage": 50,
                "quota_limit": 100,
                "quota_last_reset_date": last_month.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    print(f"   Before: quota_usage=50, quota_last_reset_date={last_month.strftime('%Y-%m')}")
    await check_and_reset_quota(db, test_org_id)
    
    plan_doc = await get_organization_plan(db, test_org_id)
    if plan_doc:
        usage_after = plan_doc.get('quota_usage', -1)
        reset_date = plan_doc.get('quota_last_reset_date')
        if isinstance(reset_date, str):
            reset_date = datetime.fromisoformat(reset_date.replace('Z', '+00:00'))
        print(f"   After:  quota_usage={usage_after}, quota_last_reset_date={reset_date.strftime('%Y-%m') if reset_date else 'N/A'}")
        
        if usage_after == 0:
            print("   ✅ Reset başarılı!")
        else:
            print("   ❌ Reset başarısız!")
    
    # Test case 2: Aynı ay (reset gerekmez)
    print("\n📋 Test Case 2: Aynı ay (reset gerekmez)")
    this_month = datetime.now(timezone.utc)
    
    await db.organization_plans.update_one(
        {"organization_id": test_org_id},
        {
            "$set": {
                "quota_usage": 30,
                "quota_last_reset_date": this_month.isoformat(),
            }
        }
    )
    
    print(f"   Before: quota_usage=30, quota_last_reset_date={this_month.strftime('%Y-%m')}")
    await check_and_reset_quota(db, test_org_id)
    
    plan_doc = await get_organization_plan(db, test_org_id)
    if plan_doc:
        usage_after = plan_doc.get('quota_usage', -1)
        print(f"   After:  quota_usage={usage_after}")
        
        if usage_after == 30:
            print("   ✅ Reset yapılmadı (doğru!)")
        else:
            print("   ❌ Reset yapıldı (yanlış!)")
    
    # Cleanup
    await db.organization_plans.delete_one({"organization_id": test_org_id})
    client.close()
    
    print("\n✅ Quota reset logic test completed!")


async def test_webhook_price_metadata():
    """Test 4: Webhook Price Metadata (Simulation)"""
    print("\n" + "="*70)
    print("TEST 4: Webhook Price Metadata Simulation")
    print("="*70)
    
    if not STRIPE_SECRET_KEY:
        print("⚠️  STRIPE_SECRET_KEY tanımlı değil, test atlanıyor")
        return
    
    # Test: Bir price'ın metadata'sını kontrol et
    # Not: Stripe'da "standart" kullanılıyor (Türkçe), "standard" değil
    test_lookup_keys = ['standart_monthly_try', 'standart_monthly_gbp']
    
    for lookup_key in test_lookup_keys:
        try:
            price = get_stripe_price_by_lookup_key(lookup_key)
            if price:
                metadata = price.metadata or {}
                appointment_limit = metadata.get('appointment_limit')
                
                print(f"\n📋 Price: {lookup_key}")
                print(f"   Price ID: {price.id}")
                print(f"   Currency: {price.currency.upper()}")
                print(f"   Amount: {price.unit_amount/100} {price.currency.upper()}")
                print(f"   Metadata: {metadata}")
                
                if appointment_limit:
                    print(f"   ✅ appointment_limit found: {appointment_limit} (Monthly Capacity)")
                else:
                    print(f"   ⚠️  appointment_limit NOT found in metadata!")
                    print(f"      💡 Stripe Dashboard'da bu price'a metadata eklemeniz gerekiyor:")
                    print(f"         Key: appointment_limit")
                    print(f"         Value: 100 (veya ilgili limit)")
        except Exception as e:
            print(f"❌ Error checking {lookup_key}: {e}")
    
    print("\n✅ Webhook price metadata test completed!")


async def main():
    """Main test function"""
    print("\n" + "="*70)
    print("🧪 STRIPE QUOTA & RESET TEST SUITE")
    print("="*70)
    
    try:
        # Test 1: Lookup key generation
        await test_lookup_key_generation()
        
        # Test 2: Stripe price lookup
        await test_stripe_price_lookup()
        
        # Test 3: Quota reset logic
        await test_quota_reset_logic()
        
        # Test 4: Webhook price metadata
        await test_webhook_price_metadata()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETED!")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Test hatası: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

