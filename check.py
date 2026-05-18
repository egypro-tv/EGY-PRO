import json
import asyncio
import aiohttp
import sys
import time
from pathlib import Path

# ====================== إعدادات ======================
WALLETS_FILE = "wallets.json"
BALANCE_FILE = "balance.json"
MAX_RETRIES = 1000  # أقصى عدد من المحاولات لكل عنوان
CHECK_INTERVAL = 2  # seconds to wait before rechecking the file
MAX_EMPTY_CHECKS = 3  # عدد المرات التي نتحقق فيها من الملف الفارغ قبل الإغلاق

RPCS = [
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXQf87QmGjQR8K9Wokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXQTDbYlGjQR8K9Vokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXQJEJBkGjQR8K9Uokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXQCFE1zGjQR8K9Tokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXT5V2WeGjMR8K9Sokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXTvYrS7GjMR8K9Rokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXTfWY6VGjMR8K9Qokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXTXQWm8GjMR8K9Pokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXTOyr7RGjMR8K9Ookw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXTGU24IGjMR8K9Nokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXS9h-MJGjMR8K9Mokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXSwcwMSGjMR8K9Lokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXSndhlhGjMR8K9Kokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXSXrRFHGjMR8K9Jokw6Xrs6",
    "https://lb.drpc.live/ethereum/AuiJy5RCIUinsY7emm1sRXSJuMdQGjMR8K9Iokw6Xrs6",
]

# ====================== تحميل المحافظ من الملف ======================
def load_wallets_from_file(file_path: str):
    """Load wallets from file and return them as a dictionary"""
    path = Path(file_path)
    if not path.exists():
        return {}, []
    
    wallets_map = {}
    all_lines = []
    
    with open(path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    for line in all_lines:
        line_stripped = line.strip()
        if line_stripped:
            try:
                wallet = json.loads(line_stripped)
                if isinstance(wallet, dict) and "address" in wallet:
                    wallets_map[wallet["address"]] = wallet
            except json.JSONDecodeError:
                continue
    
    return wallets_map, all_lines

# ====================== حذف العناوين المعالجة ======================
def remove_processed_addresses(processed_addresses, original_lines):
    """Remove lines containing processed addresses from wallets.json"""
    if not processed_addresses:
        return 0
    
    file_path = Path(WALLETS_FILE)
    new_lines = []
    removed_count = 0
    
    for line in original_lines:
        line_stripped = line.strip()
        if line_stripped:
            try:
                wallet = json.loads(line_stripped)
                if isinstance(wallet, dict) and "address" in wallet:
                    if wallet["address"] in processed_addresses:
                        removed_count += 1
                        print(f"  🗑️ حذف: {wallet['address'][:15]}...")
                        continue  # تخطي هذا السطر (حذفه)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            except json.JSONDecodeError:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # كتابة الملف بالأسطر المتبقية
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    return removed_count

# ====================== حفظ المحفظة ======================
def save_wallet_to_balance(wallet_data: dict, balance_file: str):
    file_path = Path(balance_file)
    
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(wallet_data, ensure_ascii=False) + '\n')

# ====================== فحص الرصيد ======================
async def fetch_balance(session, address, rpc_list, semaphore, wallet_data):
    """Fetch balance for a single address"""
    
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            rpc = rpc_list[attempt % len(rpc_list)]
            
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [address, "latest"],
                "id": 1
            }
            
            try:
                async with session.post(rpc, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        result_text = await response.text()
                        result_json = json.loads(result_text)
                        
                        if "error" in result_json and result_json["error"]:
                            error_msg = result_json["error"].get("message", "Unknown RPC error")
                            print(f"⚠️ {address[:10]}... | RPC Error: {error_msg[:40]}")
                            continue
                        
                        balance_hex = result_json.get('result', '0x0')
                        balance_dec = int(balance_hex, 16) / 10**18
                        
                        if balance_dec > 0:
                            if wallet_data:
                                save_wallet_to_balance(wallet_data, BALANCE_FILE)
                                print(f"💰 {address[:15]}... | {balance_dec:.8f} ETH - تم الحفظ!")
                            else:
                                print(f"⚠️ {address[:15]}... | {balance_dec:.8f} ETH - لا توجد بيانات")
                        else:
                            print(f"🟰 {address[:15]}... | 0 ETH")
                        
                        return True
                    
            except asyncio.TimeoutError:
                print(f"⏰ {address[:10]}... | Timeout (attempt {attempt + 1})")
            except Exception as e:
                print(f"❌ {address[:10]}... | Error: {str(e)[:30]}")
            
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)
        
        print(f"💀 {address[:15]}... | فشل بعد {MAX_RETRIES} محاولة")
        return False

# ====================== معالجة مجموعة واحدة من المحافظ ======================
async def process_wallets_batch(wallets_map, batch_num):
    """Process a single batch of wallets"""
    
    addresses = list(wallets_map.keys())
    print(f"\n{'='*60}")
    print(f"📦 BATCH #{batch_num} - {len(addresses)} عنوان للفحص")
    print(f"{'='*60}\n")
    
    if not addresses:
        return set()
    
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
    semaphore = asyncio.Semaphore(30)
    processed_addresses = set()
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for address in addresses:
            wallet_data = wallets_map.get(address)
            task = fetch_balance(session, address, RPCS, semaphore, wallet_data)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # جمع العناوين التي تمت معالجتها (كلها تعتبر معالجة)
        for address in addresses:
            processed_addresses.add(address)
    
    return processed_addresses

# ====================== الدالة الرئيسية ======================
async def main():
    print(f"""
╔══════════════════════════════════════════════════════╗
║     محقق الأرصدة - يعمل بشكل مستمر                   ║
║     الملف: {WALLETS_FILE}                             ║
║     سيتم الفحص تلقائياً عند إضافة عناوين جديدة       ║
╚══════════════════════════════════════════════════════╝
    """)
    
    batch_number = 1
    empty_checks = 0
    
    while True:
        # تحميل المحافظ من الملف
        wallets_map, original_lines = load_wallets_from_file(WALLETS_FILE)
        
        if not wallets_map:
            empty_checks += 1
            print(f"\n⏳ الملف {WALLETS_FILE} فارغ (التحقق #{empty_checks})")
            
            if empty_checks >= MAX_EMPTY_CHECKS:
                print(f"\n✨ الملف فارغ لـ {MAX_EMPTY_CHECKS} مرات متتالية، إنهاء البرنامج...")
                break
            
            print(f"⏰ انتظار {CHECK_INTERVAL} ثانية لظهور عناوين جديدة...")
            await asyncio.sleep(CHECK_INTERVAL)
            continue
        
        # إعادة تعيين عداد الفارغ لأن فيه عناوين
        empty_checks = 0
        
        # معالجة هذه المجموعة من المحافظ
        processed = await process_wallets_batch(wallets_map, batch_number)
        
        # حذف العناوين المعالجة من الملف
        if processed:
            print(f"\n🗑️ جاري حذف {len(processed)} عنوان من {WALLETS_FILE}...")
            removed = remove_processed_addresses(processed, original_lines)
            print(f"✅ تم حذف {removed} سطر من الملف")
        
        print(f"\n📊 إجمالي المحافظ المحفوظة في {BALANCE_FILE}:")
        try:
            with open(BALANCE_FILE, 'r', encoding='utf-8') as f:
                balance_count = sum(1 for line in f if line.strip())
            print(f"   💰 {balance_count} محفظة برصيد")
        except:
            print("   💰 0 محفظة برصيد")
        
        batch_number += 1
        
        # انتظار قليل قبل التحقق من وجود عناوين جديدة
        print(f"\n⏰ انتظار {CHECK_INTERVAL} ثانية قبل التحقق من وجود عناوين جديدة...")
        await asyncio.sleep(CHECK_INTERVAL)
        
        # التحقق مما إذا كان الملف لا يزال يحتوي على عناوين (تمت إضافتها أثناء المعالجة)
        new_check, _ = load_wallets_from_file(WALLETS_FILE)
        if new_check:
            print(f"🔄 تم اكتشاف {len(new_check)} عنوان جديد، استمرار العمل...")
        else:
            print(f"📭 لم يتم اكتشاف عناوين جديدة، ننتظر...")
    
    print(f"\n🎉 البرنامج انتهى! تم فحص جميع العناوين")
    print(f"📁 النتائج محفوظة في: {BALANCE_FILE}")

# ====================== تشغيل الكود ======================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ تم إيقاف البرنامج بواسطة المستخدم")
    except Exception as e:
        print(f"\n❌ خطأ غير متوقع: {e}")
    finally:
        input("\nاضغط Enter للإغلاق...")
