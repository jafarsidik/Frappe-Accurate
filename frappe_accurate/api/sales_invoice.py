import frappe
import requests
import hmac
import hashlib
import base64
import json
from datetime import datetime
from frappe_accurate.api.auth import get_headers,get_settings,host_token


@frappe.whitelist(allow_guest=True)
def save_do(**kwargs):
	"""
	Simpan Sales Invoice ke Accurate API
	Bisa dipanggil dari Frappe JS (frappe.call) atau Python
	"""

	host = host_token()  # ambil host terbaru via /api-token.do
	url = f"{host}/accurate/api/sales-invoice/save.do"
	headers = get_headers()

	# Ambil data dari args (kwargs)
	data_post = {}
	
	# Expand items kalau ada
	items = kwargs.pop("items", None)
	if items:
		if isinstance(items, str):
			try:
				items = json.loads(items)  # kalau datangnya string dari JS
			except Exception:
				frappe.throw("Format items tidak valid (harus list atau JSON string)")

		for i, item in enumerate(items):
			data_post[f"detailItem[{i}].itemNo"] = item.get("itemNo")
			data_post[f"detailItem[{i}].unitPrice"] = item.get("unitPrice")
			data_post[f"detailItem[{i}].quantity"] = item.get("quantity")
			if item.get("detailName"):
				data_post[f"detailItem[{i}].detailName"] = item.get("detailName")
			if item.get("warehouseName"):
				data_post[f"detailItem[{i}].warehouseName"] = item.get("warehouseName")
    
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
