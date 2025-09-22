import frappe
import requests
import hmac
import hashlib
import base64
from datetime import datetime

BASE_URL = "https://account.accurate.id/api"
def get_settings():
    return frappe.get_single("Accurate Settings")

def generate_signature(timestamp: str, secret_key: str) -> str:
    """
    Generate HMAC-SHA256 + Base64 untuk X-Api-Signature
    """
    message = timestamp.encode("utf-8")
    secret = secret_key.encode("utf-8")
    signature = hmac.new(secret, message, hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

def get_headers():
    """
    Generate headers untuk request Accurate API
    """
    settings = get_settings()
    api_token = settings.api_token       # API Token yang dibuat user
    secret_key = settings.signature_secret  # Signature Secret dari Accurate
    
    # Format timestamp sesuai Accurate (ISO 8601 lebih aman)
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    headers = {
        "Authorization": f"Bearer {api_token}",
        "X-Api-Timestamp": timestamp,
        "X-Api-Signature": generate_signature(timestamp, secret_key),
    }
    return headers

@frappe.whitelist()
def auth_info():
    host_url = f"{BASE_URL}/auth-info.do"
    headers = get_headers()
    res = requests.post(host_url, headers=headers, timeout=30, allow_redirects=True)
    res.raise_for_status()
    data = res.json()
    return data

@frappe.whitelist()
def host_token():
     # Step 1: cek host via /api-token.do (wajib untuk handle redirect 308)
    host_url = f"{BASE_URL}/api-token.do"
    headers = get_headers()
    res = requests.post(host_url, headers=headers, timeout=30, allow_redirects=True)
    res.raise_for_status()
    data = res.json()
    host = data["d"]["database"]["host"]
    return host
