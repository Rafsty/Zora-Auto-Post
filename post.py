import argparse
import json
import re
import requests
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from faker import Faker
from playwright.sync_api import sync_playwright

fake = Faker()
VIEW_POST_PAGE_WAIT_MS = 5000  # waktu ekstra setelah klik View post agar URL final siap dibaca

def dismiss_popups(page):
    popup_selectors = [
        '[data-testid="modal-close-button"]',
        '[aria-label="Close"]',
        'button[aria-label="Close"]',
        'button:has-text("Close")',
        'button:has-text("Dismiss")',
        'button:has-text("Got it")',
        'button:has-text("Skip")',
        'button:has-text("Maybe later")',
        'button:has-text("Not now")',
        'button:has-text("No thanks")',
        'button:has-text("Continue")',
        'button:has-text("OK")',
        'button:has-text("Okay")',
        'button:has-text("Thanks")',
    ]

    dismissed = False
    for selector in popup_selectors:
        try:
            locator = page.locator(selector)
            count = locator.count()
            if count == 0:
                continue
            locator.first.click(force=True)
            dismissed = True
            page.wait_for_timeout(500)
        except Exception:
            continue

    for _ in range(2):
        try:
            page.keyboard.press("Escape")
            dismissed = True
            page.wait_for_timeout(200)
        except Exception:
            break

    if not dismissed:
        try:
            viewport = page.viewport_size or {"width": 800, "height": 600}
            page.mouse.click(viewport["width"] // 2, viewport["height"] // 2)
            page.wait_for_timeout(200)
        except Exception:
            pass


def read_mail_credentials():
    """Tetap ada untuk kompatibilitas (mengambil akun pertama)."""
    try:
        with open('mail.txt', 'r') as f:
            line = f.readline().strip()
            email, password = line.split('|')
            return email.strip(), password.strip()
    except Exception as e:
        print(f"Error reading mail.txt: {e}")
        return None, None


def read_all_mail_credentials(path='mail.txt'):
    creds = []
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or '|' not in line:
                    continue
                email, password = line.split('|', 1)
                email = email.strip()
                password = password.strip()
                if email and password:
                    creds.append((email, password))
    except Exception as exc:
        print(f"Gagal membaca daftar akun dari {path}: {exc}")
    return creds


def login_mailtm(email, password):
    r = requests.post(
        "https://api.mail.tm/token",
        json={"address": email, "password": password}
    )
    return r.json().get("token")


def parse_created_at(value):
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def check_inbox_mailtm(token, min_created_at=None):
    r = requests.get(
        "https://api.mail.tm/messages",
        headers={"Authorization": f"Bearer {token}"}
    )
    messages = r.json().get("hydra:member", [])

    for msg in reversed(messages):
        created_at = parse_created_at(msg.get("createdAt"))
        if min_created_at and (not created_at or created_at < min_created_at):
            continue
        code = read_email_message(token, msg["id"])
        if code:
            return code
    return None


def read_email_message(token, msg_id):
    r = requests.get(
        f"https://api.mail.tm/messages/{msg_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    text = r.json().get("text", "")
    match = re.search(r"\b\d{6}\b", text)
    return match.group(0) if match else None


def record_post_info(email, ticker, contract_address, output_path="info_post.txt"):
    """Simpan catatan akun yang berhasil posting: email|ticker|CA."""
    if not email or not ticker:
        return
    ca_value = contract_address or "-"
    line = f"{email}|{ticker}|{ca_value}\n"
    try:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
        print(f"Info posting dicatat di {path}: {line.strip()}")
    except Exception as exc:
        print(f"Gagal menyimpan info posting: {exc}")


def extract_username_from_payload(data):
    """Cari username secara rekursif dalam payload request."""
    if isinstance(data, dict):
        username = data.get("username")
        if isinstance(username, str) and username.strip():
            return username
        for value in data.values():
            found = extract_username_from_payload(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = extract_username_from_payload(item)
            if found:
                return found
    return None


def load_settings(path="info.txt"):
    """Baca file settings sederhana agar mudah mengganti ticker/title."""
    settings = {}
    p = Path(path)
    if not p.exists():
        return settings
    try:
        for raw_line in p.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            settings[key.strip().lower()] = value.strip()
    except Exception as exc:
        print(f"Gagal membaca settings dari {path}: {exc}")
    return settings


def prompt_with_default(question, default_value):
    prompt_text = f"{question} [default: {default_value}]: "
    try:
        value = input(prompt_text)
    except EOFError:
        return default_value
    value = (value or "").strip()
    return value or default_value


def prompt_integer(question, default_value, min_value=0):
    while True:
        try:
            raw = input(f"{question} [default: {default_value}]: ")
        except EOFError:
            return default_value
        value = (raw or "").strip()
        if not value:
            return default_value
        try:
            number = int(value)
            if number < min_value:
                raise ValueError
            return number
        except ValueError:
            print(f"Masukkan angka >= {min_value}.")


def prompt_initial_settings(args):
    print("\n=== Pengaturan Awal ===")
    args.ticker = prompt_with_default("Ticker yang digunakan", args.ticker)
    args.title = prompt_with_default("Title koleksi", args.title)

    image_default = args.image or "(generate otomatis)"
    try:
        image_input = input(f"Nama file gambar (ketik 'none' untuk mode generate) [default: {image_default}]: ")
    except EOFError:
        image_input = ""
    image_input = (image_input or "").strip()
    if image_input and image_input.lower() in {"none", "generate", "-"}:
        args.image = ""
    elif image_input:
        args.image = image_input

    args.start_index = prompt_integer("Mulai dari akun nomor berapa?", args.start_index, min_value=1)
    args.ticker_group_start = prompt_integer(
        "Mulai nomor penomoran ticker dari angka berapa?",
        args.ticker_group_start,
        min_value=0,
    )



def format_cookie_headers(cookies):
    parts = []
    domain_map = {}
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        domain = cookie.get("domain", "").lstrip(".")
        if not name:
            continue
        pair = f"{name}={value}"
        parts.append(pair)
        if domain:
            domain_map.setdefault(domain, []).append(pair)
    header_all = "; ".join(parts)
    domain_headers = {domain: "; ".join(pairs) for domain, pairs in domain_map.items()}
    return header_all, domain_headers


def export_cookies(page, output_path):
    state = page.context.storage_state()
    cookies = state.get("cookies", [])
    header_all, domain_headers = format_cookie_headers(cookies)

    local_storage = {}
    for origin in state.get("origins", []):
        origin_name = origin.get("origin")
        entries = origin.get("localStorage") or []
        if not origin_name or not entries:
            continue
        local_storage[origin_name] = {
            entry.get("name"): entry.get("value") for entry in entries if entry.get("name")
        }

    try:
        session_storage = page.evaluate(
            "() => {"
            "const data = {};"
            "for (let i = 0; i < sessionStorage.length; i++) {"
            "  const key = sessionStorage.key(i);"
            "  data[key] = sessionStorage.getItem(key);"
            "}"
            "return data;"
            "}"
        )
    except Exception:
        session_storage = {}

    try:
        next_data = page.evaluate("() => window.__NEXT_DATA__ || null")
    except Exception:
        next_data = None

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "cookies": cookies,
        "cookie_header": header_all,
        "cookie_header_by_domain": domain_headers,
        "local_storage": local_storage,
        "session_storage": session_storage,
        "next_data": next_data,
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Cookies + storage disimpan ke {path}")


def try_click_upload_triggers(page):
    """Coba klik tombol/tab upload supaya input file muncul."""
    trigger_selectors = [
        'button:has-text("Upload")',
        'button:has-text("Import")',
        'button:has-text("Start with upload")',
        'button:has-text("Add media")',
        '[data-testid="upload-button"]',
    ]
    for selector in trigger_selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                locator.first.click()
                page.wait_for_timeout(500)
                return True
        except Exception:
            continue
    return False


def upload_image_asset(page, image_path: Path):
    print(f"Mengunggah gambar: {image_path}")
    try_click_upload_triggers(page)

    upload_selectors = [
        'input[type="file"][accept*="image"]',
        'input[type="file"][accept*="png"]',
        'input[type="file"][accept*="jpg"]',
        'input[type="file"]',
    ]

    for selector in upload_selectors:
        try:
            inputs = page.locator(selector)
            count = inputs.count()
            if count == 0:
                continue
            for idx in range(count):
                try:
                    inputs.nth(idx).set_input_files(str(image_path))
                    print(f"Input file via selector {selector} index {idx}")
                    page.wait_for_timeout(2000)
                    return True
                except Exception:
                    continue
        except Exception:
            continue

    print("Gagal menemukan input file untuk upload gambar.")
    return False


def extract_contract_address_from_url(url):
    """Ambil contract address (0x...) dari URL Zora."""
    if not url:
        return None
    sanitized = url.split("?", 1)[0]
    colon_idx = sanitized.rfind(":")
    if colon_idx != -1:
        candidate = sanitized[colon_idx + 1 :].strip().strip("/")
        if re.fullmatch(r"0x[a-fA-F0-9]{40}", candidate):
            return candidate
    match = re.search(r"(0x[a-fA-F0-9]{40})", sanitized)
    if match:
        return match.group(1)
    return None


def open_view_post(page, wait_timeout_ms=15000, page_ready_wait_ms=VIEW_POST_PAGE_WAIT_MS):
    """Klik tombol View post setelah proses posting selesai dan kembalikan URL + CA."""
    max_seconds = wait_timeout_ms / 1000
    print(f"Mencari tombol View post (maks {max_seconds:.1f} detik)...")
    selector_candidates = [
        'button:has-text("View post")',
        'button:has(div:has-text("View post"))',
        'button.Actionable_root__B89VV:has-text("View post")',
        '[data-testid="view-post"]',
    ]

    def wait_for_view_post_page(target_page, context_desc):
        try:
            target_page.wait_for_load_state("domcontentloaded", timeout=wait_timeout_ms)
        except Exception:
            pass

        if page_ready_wait_ms > 0:
            wait_seconds = page_ready_wait_ms / 1000
            print(f"Menunggu {wait_seconds:.1f} detik agar halaman View post di {context_desc} siap dibaca...")
            try:
                target_page.wait_for_timeout(page_ready_wait_ms)
            except Exception:
                pass

        try:
            final_url = target_page.url
        except Exception:
            final_url = ""
        return final_url

    def click_and_report(locator, selector_label):
        try:
            existing_ids = {id(p) for p in page.context.pages}
            locator.click()
            page.wait_for_timeout(1500)
            new_pages = [p for p in page.context.pages if id(p) not in existing_ids]
            target_page = page
            context_desc = "tab saat ini"
            if new_pages:
                target_page = new_pages[-1]
                context_desc = "tab baru"
            resolved_url = wait_for_view_post_page(target_page, context_desc)
            print(f"View post dibuka di {context_desc}: {resolved_url}")
            contract_address = extract_contract_address_from_url(resolved_url)
            if contract_address:
                print(f"Contract address terdeteksi: {contract_address}")
            else:
                print("Belum berhasil membaca contract address dari URL View post.")
            return resolved_url, contract_address
        except Exception as exc:
            print(f"Gagal klik tombol View post ({selector_label}): {exc}")
            return None

    deadline = time.time() + max_seconds
    while time.time() < deadline:
        try:
            locator = page.get_by_role("button", name=re.compile("View post", re.IGNORECASE))
            if locator.count() > 0:
                result = click_and_report(locator.first, "role=button[name~='View post']")
                if result:
                    return result
        except Exception:
            pass

        for selector in selector_candidates:
            try:
                locator = page.locator(selector)
                if locator.count() > 0:
                    result = click_and_report(locator.first, selector)
                    if result:
                        return result
            except Exception:
                continue

        page.wait_for_timeout(500)

    print("Tombol View post tidak ditemukan, lanjutkan proses lainnya.")
    return None, None


def automate_account(
    cookies_out=None,
    login_only=False,
    image_path=None,
    title_text=None,
    ticker_text=None,
    email=None,
    password=None,
    ticker_number=None,
):
    if not email or not password:
        email, password = read_mail_credentials()
    if not email or not password:
        print("Gagal membaca mail.txt")
        return

    image_file = None
    if image_path:
        image_file = Path(image_path).expanduser()
        if not image_file.exists():
            print(f"File gambar tidak ditemukan: {image_file}")
            return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})
        username_capture = {"value": None}
        target_request_keyword = "create.createCreateERC20UserOperationV2"

        def cache_username_from_request(request):
            if target_request_keyword not in request.url:
                return
            try:
                method = request.method
            except Exception:
                return
            if method.upper() != "POST":
                return
            payload = None
            try:
                payload = request.post_data_json()
            except Exception:
                pass
            if payload is None:
                try:
                    raw = request.post_data()
                except Exception:
                    raw = None
                if raw:
                    try:
                        payload = json.loads(raw)
                    except Exception:
                        payload = None
            if not isinstance(payload, dict):
                return
            username = extract_username_from_payload(payload)
            if username:
                username_capture["value"] = username
                print(f"Username terdeteksi dari payload request: {username}")

        page.on("request", cache_username_from_request)

        # 1. Buka website Zora
        print("1. Membuka zora.co...")
        page.goto("https://zora.co", wait_until="networkidle", timeout=45000)
        print(f"Menggunakan email: {email}")

        # 2. Klik tombol "+"
        print("2. Mencari tombol +...")
        page.wait_for_timeout(3000)

        plus_selectors = [
            'button:has(svg path[stroke="currentColor"][d*="128"])',
            'button.Actionable_root__B89VV.Button_--color-neutral',
            'button[style*="padding: 12px"]',
            'button:has(svg)',
            '[data-testid="create-button"]'
        ]

        plus_clicked = False
        for selector in plus_selectors:
            try:
                if page.locator(selector).count() > 0:
                    print(f"  [OK] Ditemukan dengan selector: {selector}")
                    page.locator(selector).first.click()
                    plus_clicked = True
                    break
            except Exception:
                continue

        if not plus_clicked:
            print("[X] Tombol + tidak ditemukan")
            page.pause()
            return

        # 3. Klik "Continue with email"
        print("3. Mencari tombol Continue with email...")
        page.wait_for_timeout(2000)

        email_selectors = [
            'button:has-text("Continue with email")',
            'button:has(div:has-text("Continue with email"))',
            'button.login-method-button',
            'button:has(svg):has(div:has-text("email"))',
            '[class*="login-method-button"]'
        ]

        email_clicked = False
        for selector in email_selectors:
            try:
                if page.locator(selector).count() > 0:
                    print(f"  [OK] Ditemukan dengan selector: {selector}")
                    page.locator(selector).first.click(force=True)
                    email_clicked = True
                    break
            except Exception:
                continue

        if not email_clicked:
            print("[X] Tombol email tidak ditemukan")
            page.pause()
            return

        # 4. Isi email
        print("4. Mengisi email...")
        page.locator("input#email-input").wait_for(state="visible", timeout=10000)
        page.locator("input#email-input").fill(email)

        # 5. Klik Submit
        print("5. Klik Submit...")
        submit_selectors = [
            'button.StyledEmbeddedButton-sc-172643dd-6',
            'button:has(span:has-text("Submit"))',
            'button:has-text("Submit")',
            'button[type="submit"]',
            '[class*="StyledEmbeddedButton"]'
        ]

        submit_clicked = False
        for selector in submit_selectors:
            try:
                if page.locator(selector).count() > 0:
                    print(f"  [OK] Submit ditemukan dengan selector: {selector}")
                    page.locator(selector).first.click(force=True)
                    submit_clicked = True
                    break
            except Exception:
                continue

        if not submit_clicked:
            print("[X] Tombol Submit tidak ditemukan")
            page.pause()
            return

        # 6. Mail.tm OTP logic
        print("6. Menunggu OTP...")
        otp_wait_start = datetime.now(timezone.utc)
        token = login_mailtm(email, password)
        if not token:
            print("Gagal login mail.tm")
            browser.close()
            return

        otp_code = None
        for i in range(10):
            otp_code = check_inbox_mailtm(token, min_created_at=otp_wait_start)
            if otp_code:
                print(f"OTP ditemukan: {otp_code}")
                break
            print(f"Mencari OTP... ({i + 1}/10)")
            time.sleep(6)

        if not otp_code:
            print("OTP tidak ditemukan")
            browser.close()
            return

        # 7. Isi OTP
        print("7. Mengisi OTP...")
        for i, digit in enumerate(otp_code):
            page.locator(f'input[name="code-{i}"]').fill(digit)
            time.sleep(0.2)

        page.wait_for_timeout(3000)

        print("Menutup pop-up jika muncul...")
        dismiss_popups(page)

        print("Lewati proses deteksi username, gunakan email sebagai identifier.")

        if cookies_out:
            export_cookies(page, cookies_out)

        if login_only:
            print("Mode login-only aktif. Cookies diekspor, menghentikan otomatisasi.")
            browser.close()
            return

        # 8. Cek & klik "Start trading" jika ada
        print("8. Cek tombol Start trading...")
        trading_selectors = [
            'button:has-text("Start trading")',
            'button.Button_--color-primary:has(span:has-text("Start trading"))',
            'button:has(span:has-text("Start trading"))'
        ]

        trading_clicked = False
        for selector in trading_selectors:
            try:
                if page.locator(selector).count() > 0:
                    print(f"  [OK] Tombol Start trading ditemukan! Selector: {selector}")
                    page.locator(selector).first.click(force=True)
                    trading_clicked = True
                    print("  [OK] Start trading berhasil diklik!")
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

        if not trading_clicked:
            print("  >> Tombol Start trading tidak ada, lanjutkan...")
            page.wait_for_timeout(1500)

        # 9. Cek tombol + pre-generate
        print("9. Cek tombol + pre-generate...")
        pregenerate_plus_selectors = [
            'button:has(svg path[d*="M40 128h176M128 40v176"])',
            'button.Actionable_root__B89VV.Button_--color-neutral__iK_CE.Button_--variant-ghost__QGLMd',
            'button[style*="padding: 12px"][style*="background-color: var(--rs-color-background-neutral-faded)"]',
            'button:has(svg):has([class*="Icon_root__E_X7_"])',
            'button:has(span[aria-hidden="true"] svg)'
        ]

        pregenerate_plus_clicked = False
        for selector in pregenerate_plus_selectors:
            try:
                if page.locator(selector).count() > 0:
                    print(f"  [OK] Tombol + pre-generate ditemukan! Selector: {selector}")
                    page.locator(selector).first.click(force=True)
                    pregenerate_plus_clicked = True
                    print("  [OK] Tombol + pre-generate berhasil diklik!")
                    page.wait_for_timeout(45000)
                    break
            except Exception:
                continue

        if not pregenerate_plus_clicked:
            print("  >> Tombol + pre-generate tidak ada, lanjutkan...")
            page.wait_for_timeout(45000)

        use_upload = image_file is not None

        if use_upload:
            print("10. Upload gambar dari file...")
            if not upload_image_asset(page, image_file):
                error_message = "Upload gambar gagal, skip akun ini dan lanjut akun berikutnya."
                print(error_message)
                raise RuntimeError(error_message)
            page.wait_for_timeout(3000)
        else:
            # 10. Cek tombol Generate (ghost)
            print("10. Cek tombol Generate (ghost)...")
            generate_ghost_selectors = [
                'button.Button_--color-neutral-faded__Wn8DX:has-text("Generate")',
                'button.Actionable_root__B89VV.Button_--color-neutral-faded__Wn8DX:has(span:has-text("Generate"))',
                'button.Button_--variant-ghost:has(span:has-text("Generate"))'
            ]

            generate_ghost_clicked = False
            for selector in generate_ghost_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        print(f"  [OK] Generate ghost ditemukan! Selector: {selector}")
                        page.locator(selector).first.click(force=True)
                        generate_ghost_clicked = True
                        print("  [OK] Generate ghost berhasil diklik!")
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            if not generate_ghost_clicked:
                print("  >> Tombol Generate ghost tidak ada, lanjutkan...")
                page.wait_for_timeout(1500)

            # 11. RANDOM STYLE SELECTOR
            print("11. Pilih style secara random...")
            style_buttons = page.locator('button.Actionable_root__B89VV:has(div.Text_root__LZy0C)')

            button_count = style_buttons.count()
            print(f"  Total style buttons found: {button_count}")

            if button_count > 0:
                random_index = random.randint(0, button_count - 1)
                print(f"  Memilih style #{random_index + 1}")
                style_buttons.nth(random_index).scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                style_buttons.nth(random_index).click(force=True)
                print("  [OK] Style random berhasil dipilih!")
                page.wait_for_timeout(1500)
            else:
                print("  Tidak ada style buttons ditemukan, skip...")
                all_actionable = page.locator('button.Actionable_root__B89VV')
                print(f"  Debug: Total Actionable buttons: {all_actionable.count()}")
                page.wait_for_timeout(1000)

            # 12. Isi prompt
            print("12. Mengisi prompt...")
            page.locator(
                'textarea[name="prompt"], textarea[placeholder*="prompt"]'
            ).fill(fake.sentence(nb_words=10))
            page.wait_for_timeout(1500)

            # 13. Generate utama
            print("13. Generate utama...")
            generate_selectors = [
                'button.Button_--color-primary:has-text("Generate")',
                'button.Button_--variant-solid:has-text("Generate")',
                'button.Button_--size-xlarge:has-text("Generate")',
                'button[type="submit"]:has-text("Generate")',
                'button:has-text("Generate")'
            ]

            generate_clicked = False
            for selector in generate_selectors:
                try:
                    generate_btn = page.locator(selector).first
                    if generate_btn.count() > 0:
                        generate_btn.wait_for(state="visible", timeout=5000)
                        if generate_btn.is_enabled():
                            generate_btn.click(force=True)
                            print(f"  [OK] Generate berhasil! Selector: {selector}")
                            generate_clicked = True
                            break
                except Exception as e:
                    print(f"  Skip selector {selector}: {e}")
                    continue

            if not generate_clicked:
                print("  [X] Semua Generate selector gagal")
                page.pause()
                return

            print("Menunggu image generate...")
            page.wait_for_load_state("networkidle", timeout=45000)
            page.wait_for_timeout(3000)
        # 14. Isi title & ticker (BUKAN displayName!)
        print("14. Isi title & ticker...")

        final_title = title_text or fake.word().capitalize()
        page.locator('input[name="title"]').fill(final_title)
        print(f"Title: {final_title}")
        page.wait_for_timeout(1000)

        final_ticker = (ticker_text or ''.join(fake.word().lower() for _ in range(3))[:12]).strip()
        final_ticker = final_ticker.upper()
        if ticker_number is not None:
            final_ticker = f"{final_ticker} {ticker_number}".strip()
        page.locator('input[name="ticker"]').fill(final_ticker)
        print(f"Ticker: {final_ticker}")
        page.wait_for_timeout(1000)

        # 15. Post
        print("15. Posting...")
        page.get_by_role("button", name="Post").first.click()
        print("Posting berhasil!")
        success_message = f"Akun {email} berhasil post ({final_ticker})"
        print(success_message)
        print("Menunggu 10 detik agar proses posting rampung sebelum mengambil username...")
        page.wait_for_timeout(1000)
        view_url, contract_address = open_view_post(page)
        if not view_url:
            print("View post tidak muncul => anggap posting gagal. Menutup browser.")
            browser.close()
            raise RuntimeError("View post tidak ditemukan setelah posting")

        username_wait_ms = 1000
        check_interval_ms = 500
        elapsed_ms = 0
        captured_username = username_capture.get("value")
        print("Mengecek payload request untuk username (maksimal 5 detik)...")
        while not captured_username and elapsed_ms < username_wait_ms:
            page.wait_for_timeout(check_interval_ms)
            elapsed_ms += check_interval_ms
            captured_username = username_capture.get("value")

        if captured_username:
            print(f"Username final untuk dicatat: {captured_username}")
        else:
            print("Username belum ditemukan dari payload, gunakan ticker sebagai fallback.")
            captured_username = final_ticker

        record_post_info(email, final_ticker, contract_address)

        if cookies_out and not login_only:
            export_cookies(page, cookies_out)

        print("Menutup browser setelah username tercatat.")
        browser.close()


def parse_arguments():
    parser = argparse.ArgumentParser(description="Automasi posting Zora + ekspor cookies.")
    parser.add_argument("--cookies-out", help="Path file JSON untuk menyimpan cookies hasil login.")
    parser.add_argument("--login-only", action="store_true", help="Berhenti setelah login & ekspor cookies.")
    parser.add_argument("--mail-file", default="mail.txt", help="File daftar email|password (default: mail.txt).")
    parser.add_argument("--start-index", type=int, default=1, help="Mulai dari akun ke-N (default: 1).")
    parser.add_argument("--max-accounts", type=int, help="Batas jumlah akun yang diproses.")
    parser.add_argument("--delay-between-accounts", type=float, default=5.0, help="Jeda antar akun dalam detik (default: 5).")
    parser.add_argument("--image", default="elite.png", help="Path gambar yang akan diupload (default: elite.png). Kosongkan untuk mode generate.")
    parser.add_argument("--title", default="ELITE GLOBAL", help="Judul koleksi/token (default: ELITE GLOBAL).")
    parser.add_argument("--ticker", default="ELITE GLOBAL", help="Ticker token (default: ELITE GLOBAL).")
    parser.add_argument("--ticker-group-start", type=int, default=2, help="Angka awal penomoran suffix ticker (default: 2).")
    parser.add_argument("--settings-file", default="info.txt", help="File settings tambahan (default: info.txt).")
    return parser.parse_args()


def run_accounts():
    args = parse_arguments()
    accounts = read_all_mail_credentials(args.mail_file)
    if not accounts:
        print(f"Tidak ada akun valid di {args.mail_file}")
        return

    settings = load_settings(args.settings_file)
    if settings:
        ticker_override = settings.get("ticker")
        if ticker_override:
            args.ticker = ticker_override
            print(f"Ticker diganti via {args.settings_file}: {args.ticker}")
        title_override = settings.get("title")
        if title_override:
            args.title = title_override
            print(f"Title diganti via {args.settings_file}: {args.title}")
        ticker_start_override = settings.get("ticker_group_start")
        if ticker_start_override:
            try:
                args.ticker_group_start = max(0, int(ticker_start_override))
                print(f"Ticker group start diganti via {args.settings_file}: {args.ticker_group_start}")
            except ValueError:
                print(f"Nilai ticker_group_start di {args.settings_file} tidak valid: {ticker_start_override}")

    prompt_initial_settings(args)

    start_index = max(1, args.start_index)
    processed = 0
    total = len(accounts)
    ticker_group_size = 5
    ticker_group_start = max(0, args.ticker_group_start)
    successful_posts = 0

    for idx, (email, password) in enumerate(accounts, start=1):
        if idx < start_index:
            continue
        if args.max_accounts and processed >= args.max_accounts:
            break

        print(f"\n=== Memproses akun {idx}/{total}: {email} ===")
        cookies_out_path = args.cookies_out
        if cookies_out_path and (args.max_accounts or total > 1):
            base = Path(cookies_out_path)
            suffix = base.suffix
            stem = base.stem
            new_name = f"{stem}_{idx}{suffix}"
            cookies_out_path = str(base.with_name(new_name))

        ticker_suffix = (successful_posts // ticker_group_size) + ticker_group_start

        try:
            automate_account(
                email=email,
                password=password,
                cookies_out=cookies_out_path,
                login_only=args.login_only,
                image_path=args.image if args.image else None,
                title_text=args.title,
                ticker_text=args.ticker,
                ticker_number=ticker_suffix,
            )
            successful_posts += 1
        except KeyboardInterrupt:
            print("Dihentikan oleh pengguna.")
            break
        except Exception as exc:
            print(f"Terjadi error pada akun {email}: {exc}")

        processed += 1
        if args.max_accounts and processed >= args.max_accounts:
            break
        if idx < total:
            print(f"Jeda {args.delay_between_accounts} detik sebelum akun berikutnya...")
            time.sleep(args.delay_between_accounts)


if __name__ == "__main__":
    run_accounts()
