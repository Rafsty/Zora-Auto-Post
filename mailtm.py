import requests
import random
import string
import re
from colorama import Fore

session = requests.Session()


def set_mailtm_proxy(proxies: dict | None):
    """
    Configure the requests session to use a specific proxy mapping.
    When proxies is None, system/environment proxies are respected.
    """
    session.proxies = proxies or {}
    session.trust_env = proxies is None

def get_available_domains():
    url = "https://api.mail.tm/domains"
    response = session.get(url)
    domains = response.json()["hydra:member"]
    return [d["domain"] for d in domains]

def generate_random_email_with_domain(domain):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@" + domain

def save_account_to_file(email, password):
    with open("Mail.txt", "a", encoding="utf-8") as f:
        f.write(f"{email}|{password}\n")

def create_random_mailtm_account(domains):
    domain = random.choice(domains)
    email = generate_random_email_with_domain(domain)
    password = "Katasandi123"

    r = session.post(
        "https://api.mail.tm/accounts",
        json={"address": email, "password": password}
    )

    if r.status_code == 201:
        return r.json(), password

    return None, None

def login_mailtm(email, password):
    r = session.post(
        "https://api.mail.tm/token",
        json={"address": email, "password": password}
    )
    return r.json().get("token")

def check_inbox_mailtm(token):
    r = session.get(
        "https://api.mail.tm/messages",
        headers={"Authorization": f"Bearer {token}"}
    )

    for msg in r.json().get("hydra:member", []):
        code = read_email_message(token, msg["id"])
        if code:
            return code
    return None

def read_email_message(token, msg_id):
    r = session.get(
        f"https://api.mail.tm/messages/{msg_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    text = r.json().get("text", "")
    match = re.search(r"\b\d{6}\b", text)
    return match.group(0) if match else None
