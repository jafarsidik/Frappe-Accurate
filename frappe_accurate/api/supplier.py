import frappe
import requests
import hmac
import hashlib
import base64
from datetime import datetime
from frappe_accurate.api.auth import get_headers,get_settings,host_token


@frappe.whitelist(allow_guest=True)
def save_do(**kwargs):
	"""
	Simpan Supplier ke Accurate API
	Bisa dipanggil dari Frappe JS (frappe.call) atau Python
	"""

	host = host_token()  # ambil host terbaru via /api-token.do
	url = f"{host}/accurate/api/vendor/save.do"
	headers = get_headers()

	# Ambil data dari args (kwargs)
	data_post = {}
	for key, val in kwargs.items():
		if val:  # hanya kirim field yang ada isinya
			data_post[key] = val

	if not data_post:
		frappe.throw("Tidak ada data yang dikirim ke Accurate")

	res = requests.post(url, headers=headers, data=data_post, timeout=30)
	res.raise_for_status()

	try:
		return res.json()
	except Exception:
		return {"error": res.text, "status": res.status_code}
