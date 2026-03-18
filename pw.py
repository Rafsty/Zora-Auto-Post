import asyncio
import os
import random
from playwright.async_api import async_playwright
from faker import Faker

from mailtm import (
    get_available_domains,
    create_random_mailtm_account,
    login_mailtm,
    check_inbox_mailtm,
    save_account_to_file
)

fake = Faker()

INVITE_URL = "https://zora.co/invite/170fit"
AVATAR_DIR = "avatars"


async def main():
    try:
        total_accounts = int(input("Masukkan jumlah akun: "))
    except ValueError:
        print("❌ Input harus angka")
        return

    domains = get_available_domains()
    if not domains:
        print("❌ Tidak ada domain Mail.tm")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        for idx in range(1, total_accounts + 1):
            print(f"\n🚀 MEMBUAT AKUN {idx}/{total_accounts}")

            # =====================
            # EMAIL SETUP
            # =====================
            account, password = create_random_mailtm_account(domains)
            if not account:
                print("❌ Gagal membuat email, skip akun")
                continue

            email = account["address"]
            print(f"📧 Email: {email}")

            token = login_mailtm(email, password)
            if not token:
                print("❌ Gagal login Mail.tm, skip akun")
                continue

            page = await browser.new_page()

            try:
                await page.goto(INVITE_URL, timeout=60000)

                # SIGN UP ON WEB
                await page.get_by_text("sign up on web", exact=False).click()

                # CONTINUE WITH EMAIL
                await page.get_by_text("Continue with email", exact=False).click()

                # INPUT EMAIL
                await page.fill("input[type='email']", email)
                await page.get_by_text("Submit", exact=True).click()

                # =====================
                # OTP
                # =====================
                print("⏳ Menunggu OTP...")
                otp = None
                for _ in range(15):
                    otp = check_inbox_mailtm(token)
                    if otp:
                        break
                    await asyncio.sleep(4)

                if not otp:
                    print("❌ OTP tidak diterima, skip akun")
                    await page.close()
                    continue

                print(f"✅ OTP: {otp}")

                for i, digit in enumerate(otp):
                    await page.fill(f"input[name='code-{i}']", digit)

                await page.wait_for_timeout(15000)

                # =====================
                # AVATAR UPLOAD
                # =====================
                avatars = [
                    os.path.join(AVATAR_DIR, f)
                    for f in os.listdir(AVATAR_DIR)
                    if f.lower().endswith(("png", "jpg", "jpeg", "webp"))
                ]

                if not avatars:
                    print("❌ Folder avatars kosong")
                    await page.close()
                    continue

                avatar_path = random.choice(avatars)
                print(f"🖼️ Upload avatar: {avatar_path}")

                if await page.locator("input[type='file']").count() == 0:
                    await page.locator("img[alt='Avatar']").click()
                    await page.wait_for_selector("input[type='file']", timeout=15000)

                await page.set_input_files("input[type='file']", avatar_path)

                await page.wait_for_function("""
                () => {
                  const img = document.querySelector("img[alt='Avatar']");
                  return img && img.src.includes("ipfs");
                }
                """, timeout=20000)

                print("✅ Avatar uploaded")

                # =====================
                # USERNAME LOOP (ICON + ERROR)
                # =====================
                username_input = page.locator("input[name='username']")
                error_locator = page.locator("span[role='alert']")
                success_icon = page.locator("svg path[d*='m88 136']")

                username_ok = False

                for attempt in range(1, 13):
                    suffix_length = random.randint(2, 4)
                    suffix = "".join(random.choices("0123456789", k=suffix_length))
                    username = fake.user_name() + suffix
                    await username_input.fill(username)

                    await page.wait_for_timeout(1500)

                    # ✅ icon hijau = valid
                    if await success_icon.count() > 0:
                        print(f"✅ Username VALID: {username}")
                        username_ok = True
                        break

                    # ❌ error muncul
                    if await error_locator.count() > 0:
                        print(f"⚠️ Username dipakai, retry {attempt}")
                        continue

                    # fallback (kadang UI lambat)
                    print(f"ℹ️ Username diasumsikan valid: {username}")
                    username_ok = True
                    break

                if not username_ok:
                    print("❌ Gagal mendapatkan username valid, skip akun")
                    await page.close()
                    continue

                # DISPLAY NAME
                await page.fill("input[name='displayName']", fake.name())

                # =====================
                # BACKUP WALLET (KEY + PHRASE) — SVG BASED
                # =====================
                print("🔐 Backup wallet (key + phrase)...")

                # Klik tombol Backup (AMAN dari strict mode)
                await page.get_by_role("button", name="Backup").click()
                await page.wait_for_timeout(3000)

                private_key = ""
                seed_phrase = ""

                # ---------- COPY PRIVATE KEY ----------
                copy_key_btn = page.locator(
                    "button:has(svg.lucide-key)"
                )
                if await copy_key_btn.count() > 0:
                    await copy_key_btn.first.click()
                    await page.wait_for_timeout(1000)
                    private_key = await page.evaluate(
                        "navigator.clipboard.readText()"
                    )
                    print("🔑 Private key copied")
                else:
                    print("⚠️ Tombol Copy key tidak ditemukan (SVG)")

                # ---------- COPY SEED PHRASE ----------
                copy_phrase_btn = page.locator(
                    "button:has(svg.lucide-whole-word)"
                )
                if await copy_phrase_btn.count() > 0:
                    await copy_phrase_btn.first.click()
                    await page.wait_for_timeout(1000)
                    seed_phrase = await page.evaluate(
                        "navigator.clipboard.readText()"
                    )
                    print("🧾 Seed phrase copied")
                else:
                    print("⚠️ Tombol Copy Phrase tidak ditemukan (SVG)")

                # ---------- VALIDASI & SIMPAN ----------
                if private_key and seed_phrase:
                    with open("wallet_backup.txt", "a", encoding="utf-8") as f:
                        f.write(
                            f"{email}|{username}|{private_key}|{seed_phrase}\n"
                        )
                    print("💾 Wallet berhasil disimpan")
                else:
                    print("❌ Wallet tidak lengkap, tidak disimpan")

                # ---------- CLOSE MODAL ----------
                close_btn = page.locator("button[aria-label='close modal']")
                if await close_btn.count() > 0:
                    await close_btn.first.click()
                    await page.wait_for_timeout(1000)

                # =====================
                # CREATE ACCOUNT
                # =====================
                await page.get_by_text("Create account", exact=False).click()
                await page.wait_for_timeout(15000)

                # FINISH
                await page.get_by_text("Finish", exact=True).click()
                await page.wait_for_timeout(15000)

                # ACTIVATE
                await page.get_by_text("Activate", exact=True).nth(0).click()
                await page.wait_for_timeout(15000)
                await page.get_by_text("Activate", exact=True).nth(1).click()
                await page.wait_for_timeout(50000)

                save_account_to_file(email, password)

                print(f"🎉 AKUN {idx} BERHASIL")

            except Exception as e:
                print(f"❌ ERROR AKUN {idx}: {e}")

            finally:
                await page.close()
                await asyncio.sleep(5)

        await browser.close()
        print("\n✅ SEMUA PROSES SELESAI")


asyncio.run(main())
