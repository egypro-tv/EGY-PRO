import random
import hashlib
import hmac
import binascii
import json
import time
from eth_account import Account

# تحميل قائمة كلمات BIP39
def load_bip39_words(filename="bip39.txt"):
    with open(filename, "r", encoding="utf-8") as f:
        words = [word.strip() for word in f.readlines() if word.strip()]
    return words

words = load_bip39_words()

# اسم الملف
JSON_FILE = "wallets.json"

print("بدء البحث اللامتناهي... (Ctrl+C للإيقاف)")
count = 0

while True:
    # استخراج 12 كلمة عشوائية
    mnemonic = " ".join(random.choices(words, k=12))

    # توليد Private Key من Mnemonic
    try:
        Account.enable_unaudited_hdwallet_features()
        acct = Account.from_mnemonic(mnemonic, account_path="m/44'/60'/0'/0/0")
        private_key = acct.key.hex()
        eth_address = acct.address
        
        count += 1

        # حفظ المحفظة في JSON (كل محفظة على سطر - JSON Lines)
        wallet_data = {
            "address": eth_address,
            "private_key": private_key,
            "mnemonic": mnemonic,
        }
        
        with open(JSON_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(wallet_data, ensure_ascii=False) + "\n")

        # طباعة العداد كل 1000 محفظة
        if count % 1000 == 0:
            print(f"Count: {count:,} | تم توليد {count:,} محفظة حتى الآن | تم الحفظ في {JSON_FILE}")
          
    except Exception as e:
        continue
