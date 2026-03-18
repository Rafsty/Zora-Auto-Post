import asyncio
import os
import random
from urllib.parse import urlparse
from urllib.request import getproxies
from requests.exceptions import ProxyError
from playwright.async_api import async_playwright
from faker import Faker

from mailtm import (
    get_available_domains,
    create_random_mailtm_account,
    login_mailtm,
    check_inbox_mailtm,
    save_account_to_file,
    set_mailtm_proxy
)

fake = Faker()

INVITE_URL = "https://zora.co/invite/trumpnuclearbeam"
AVATAR_DIR = "avatars"
PROXY_FILE = "proxies.txt"


def build_proxy_config(proxy_str: str | None):
    if not proxy_str:
        return None

    candidate = proxy_str.strip()
    if not candidate:
        return None

    if "://" not in candidate:
        parts = candidate.split(":")
        if len(parts) == 4:
            host, port, username, password = parts
            if host and port and username and password:
                return {
                    "server": f"http://{host}:{port}",
                    "username": username,
                    "password": password
                }
        elif len(parts) == 2:
            host, port = parts
            if host and port:
                return {"server": f"http://{host}:{port}"}

        candidate = f"http://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.hostname or not parsed.port:
        return None

    proxy = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password

    return proxy


def build_requests_proxy(proxy_config):
    if not proxy_config:
        return None

    parsed = urlparse(proxy_config["server"])
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        return None

    auth = ""
    if proxy_config.get("username"):
        password = proxy_config.get("password", "")
        auth = f"{proxy_config['username']}:{password}@"

    proxy_url = f"{parsed.scheme}://{auth}{parsed.hostname}:{parsed.port}"
    return {"http": proxy_url, "https": proxy_url}


def detect_system_proxy_url():
    proxies = getproxies()
    return proxies.get("https") or proxies.get("http")


def inject_credentials(proxy_url, username, password):
    parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
    if not parsed.hostname or not parsed.port:
        return None

    scheme = parsed.scheme or "http"
    userinfo = f"{username}:{password}@" if username else ""
    return f"{scheme}://{userinfo}{parsed.hostname}:{parsed.port}"


def load_proxy_list(file_path: str):
    if not os.path.exists(file_path):
        return []

    proxies = []
    with open(file_path, encoding="utf-8") as fp:
        for raw in fp:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            cfg = build_proxy_config(line)
            if cfg:
                proxies.append(cfg)

    return proxies


async def main():
    try:
        total_accounts = int(input("Masukkan jumlah akun: "))
    except ValueError:
        print("❌ Input harus angka")
        return

    proxy_list = load_proxy_list(PROXY_FILE)
    use_proxy_list = False
    proxy_config = None

    system_proxy_url = detect_system_proxy_url()

    if proxy_list:
        choice = input(
            f"Gunakan proxy list dari {PROXY_FILE}? (y/n): "
        ).strip().lower()
        if choice == "y":
            use_proxy_list = True
            print(f"🔁 Proxy list aktif ({len(proxy_list)} proxy).")

    use_system_proxy = False
    if not use_proxy_list and system_proxy_url:
        ans = input("Gunakan proxy dari pengaturan Windows? (y/n): ").strip().lower()
        if ans == "y":
            use_system_proxy = True
            username = input("Username proxy (kosong jika tidak perlu): ").strip()
            password = ""
            if username:
                password = input("Password proxy: ").strip()
            proxy_with_auth = system_proxy_url
            if username or password:
                proxy_with_auth = inject_credentials(system_proxy_url, username, password)
            proxy_config = build_proxy_config(proxy_with_auth)
            if proxy_config:
                print(f"🌐 Proxy sistem aktif: {proxy_config['server']}")
            else:
                print("❌ Gagal membaca proxy sistem, lanjut ke input manual.")
                use_system_proxy = False
                proxy_config = None

    if not use_proxy_list and not use_system_proxy:
        proxy_input = input(
            "Masukkan proxy tunggal (ip:port:user:pass atau http://user:pass@host:port), kosongkan jika tidak: "
        ).strip()
        proxy_config = build_proxy_config(proxy_input)
        if proxy_input and not proxy_config:
            print("❌ Format proxy tidak valid, lanjut tanpa proxy.")
        elif proxy_config:
            print(f"🌐 Proxy aktif: {proxy_config['server']}")

    initial_mailtm_proxy = proxy_config if not use_proxy_list else None
    start_proxy_idx = 0

    domains = None
    if use_proxy_list:
        for idx_proxy, proxy_conf in enumerate(proxy_list):
            set_mailtm_proxy(build_requests_proxy(proxy_conf))
            try:
                domains = get_available_domains()
                start_proxy_idx = idx_proxy
                break
            except ProxyError as e:
                print(f"❌ Proxy {proxy_conf['server']} gagal akses Mail.tm: {e}")
        if not domains:
            print("❌ Tidak bisa mengambil domain Mail.tm dengan semua proxy.")
            return
    else:
        set_mailtm_proxy(build_requests_proxy(initial_mailtm_proxy))
        try:
            domains = get_available_domains()
        except ProxyError as e:
            print(f"❌ Gagal mengakses Mail.tm lewat proxy: {e}")
            return

    if not domains:
        print("❌ Tidak ada domain Mail.tm")
        return

    async with async_playwright() as p:
        def create_launch_kwargs(proxy=None):
            kwargs = {
                "headless": True,
                "args": ["--disable-blink-features=AutomationControlled"],
            }
            if proxy:
                kwargs["proxy"] = proxy
            return kwargs

        browser = None
        if not use_proxy_list:
            browser = await p.chromium.launch(**create_launch_kwargs(proxy_config))

        for idx in range(1, total_accounts + 1):
            print(f"\n🚀 MEMBUAT AKUN {idx}/{total_accounts}")

            current_browser = browser
            if use_proxy_list:
                proxy_for_run = proxy_list[(start_proxy_idx + idx - 1) % len(proxy_list)]
                print(f"🌐 Proxy akun {idx}: {proxy_for_run['server']}")
                set_mailtm_proxy(build_requests_proxy(proxy_for_run))
                current_browser = await p.chromium.launch(
                    **create_launch_kwargs(proxy_for_run)
                )

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

            page = None

            try:
                page = await current_browser.new_page()
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
                # BACKUP WALLET (DISABLE DULU)
                # =====================
                # await page.get_by_text("Backup", exact=True).click()
                # await page.wait_for_timeout(3000)
                # ...

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
                await page.get_by_text("Activate", exact=True).nth(1).click()
                await page.wait_for_timeout(15000)

                save_account_to_file(email, password)

                print(f"🎉 AKUN {idx} BERHASIL")

            except Exception as e:
                print(f"❌ ERROR AKUN {idx}: {e}")

            finally:
                if page and not page.is_closed():
                    await page.close()
                await asyncio.sleep(5)
                if use_proxy_list and current_browser:
                    await current_browser.close()

        if not use_proxy_list and browser:
            await browser.close()
        print("\n✅ SEMUA PROSES SELESAI")


asyncio.run(main())
