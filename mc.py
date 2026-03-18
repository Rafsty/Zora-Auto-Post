import requests
import re
import time
from playwright.sync_api import sync_playwright, expect

# Mail.tm API Functions
def login_mailtm(email, password):
    try:
        r = requests.post(
            "https://api.mail.tm/token",
            json={"address": email, "password": password},
            timeout=10
        )
        return r.json().get("token")
    except:
        return None

def check_inbox_mailtm(token):
    try:
        r = requests.get(
            "https://api.mail.tm/messages",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        for msg in r.json().get("hydra:member", []):
            code = read_email_message(token, msg["id"])
            if code:
                return code
        return None
    except:
        return None

def read_email_message(token, msg_id):
    try:
        r = requests.get(
            f"https://api.mail.tm/messages/{msg_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        text = r.json().get("text", "")
        match = re.search(r"\b\d{6}\b", text)
        return match.group(0) if match else None
    except:
        return None

def get_credentials():
    try:
        with open('mail.txt', 'r') as f:
            for line in f.readlines():
                line = line.strip()
                if '|' in line:
                    email, password = line.split('|', 1)
                    yield email.strip(), password.strip()
    except FileNotFoundError:
        print("❌ File mail.txt tidak ditemukan! Format: email|password")
        return

# COMPLETE ZORA.CO AUTOMATION (9 STEPS)
def run(playwright):
    print("🚀 ZORA.CO FULL AUTOMATION START")
    print("=" * 60)
    
    # Launch browser
    browser = playwright.chromium.launch(
        headless=False, 
        slow_mo=200,
        args=['--start-maximized', '--disable-blink-features=AutomationControlled']
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page = context.new_page()
    
    # STEP 0: Get credentials
    credentials = get_credentials()
    email, password = next(credentials)
    print(f"📧 Using: {email}")
    
    token = login_mailtm(email, password)
    if not token:
        print("❌ Mail.tm login failed!")
        input("Press Enter to exit...")
        browser.close()
        return
    
    print("✅ Mail.tm ready")
    
    # STEP 1: Open Zora.co
    print("\n1️⃣ STEP 1 - Opening zora.co...")
    page.goto("https://zora.co/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(4000)
    
    # STEP 2: Click avatar login button
    print("2️⃣ STEP 2 - Clicking avatar...")
    try:
        avatar_span = page.locator('span.Button_text__X_46L:has(img[src*="default-avatar.png"])').first
        avatar_btn = avatar_span.locator('..')
        expect(avatar_span).to_be_visible(timeout=15000)
        avatar_span.scroll_into_view_if_needed()
        avatar_btn.click(force=True)
        print("✅ Avatar clicked!")
    except:
        page.click('button:has(img[src*="default-avatar.png"])', force=True)
        print("✅ Avatar fallback!")
    
    page.wait_for_timeout(3000)
    
    # STEP 3: Click "Continue with email"
    print("3️⃣ STEP 3 - Continue with email...")
    try:
        email_btn = page.locator('button.login-method-button:has-text("Continue with email")').first
        expect(email_btn).to_be_visible(timeout=10000)
        email_btn.click(force=True)
        print("✅ Email button clicked!")
    except:
        page.get_by_text("Continue with email").click(force=True)
        print("✅ Email text fallback!")
    
    page.wait_for_timeout(3000)
    
    # STEP 4: Fill email
    print("4️⃣ STEP 4 - Filling email...")
    page.locator('#email-input, input[placeholder*="email"], input[type="email"]').fill(email)
    print("✅ Email filled!")
    page.wait_for_timeout(1000)
    
    # STEP 5: Submit email
    print("5️⃣ STEP 5 - Submitting...")
    page.locator('button:has-text("Submit")').click(force=True)
    print("✅ Submitted!")
    page.wait_for_timeout(8000)
    
    # STEP 6: Auto OTP
    print("6️⃣ STEP 6 - Getting OTP...")
    otp_code = None
    for i in range(10):
        otp_code = check_inbox_mailtm(token)
        if otp_code:
            print(f"✅ OTP: {otp_code}")
            break
        print(f"⏳ Waiting OTP... ({i+1}/10)")
        time.sleep(4)
    
    if otp_code:
        for i in range(6):
            page.locator(f'input[name="code-{i}"]').fill(otp_code[i])
            page.wait_for_timeout(200)
        print("✅ OTP filled!")
    else:
        print("❌ No OTP found - manual entry:")
        input("Enter OTP manually, then press Enter...")
    
    page.wait_for_timeout(4000)
    
    # STEP 7: Start trading
    print("7️⃣ STEP 7 - Start trading...")
    try:
        trading_btn = page.locator('button:has-text("Start trading")').first
        expect(trading_btn).to_be_visible(timeout=15000)
        trading_btn.click(force=True)
        print("✅ Start trading clicked!")
    except:
        page.get_by_text("Start trading").click(force=True)
        print("✅ Trading fallback!")
    
    page.wait_for_timeout(4000)
    
    # STEP 8: Click profile avatar (choicecdn)
    print("8️⃣ STEP 8 - Profile avatar...")
    try:
        profile_avatar = page.locator('span[data-rs-aligner-target="true"]:has(img[src*="choicecdn.com"])').first
        expect(profile_avatar).to_be_visible(timeout=10000)
        profile_avatar.click(force=True)
        print("✅ Profile avatar clicked!")
    except:
        page.locator('img[src*="scontent-iad4-1.choicecdn.com"]').first.locator('..').click(force=True)
        print("✅ Profile fallback!")
    
    page.wait_for_timeout(3000)
    
    # STEP 9: Click chat button
    print("9️⃣ STEP 9 - Chat button...")
    try:
        chat_btn = page.locator('button[data-rs-aligner-target="true"].Button_--size-small__fvXTL:has(svg circle)').first
        expect(chat_btn).to_be_visible(timeout=10000)
        chat_btn.click(force=True)
        print("✅ Chat opened! 🎉")
    except:
        page.locator('button:has(svg circle[cx="180"])').click(force=True)
        print("✅ Chat fallback!")
    
    input("\n⏸️  Press Enter to close browser...")
    browser.close()

# RUN
if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
    print("✅ Script finished!")
