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
	Simpan Customer ke Accurate API
	Bisa dipanggil dari Frappe JS (frappe.call) atau Python
	"""

	host = host_token()  # ambil host terbaru via /api-token.do
	url = f"{host}/accurate/api/customer/save.do"
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

@frappe.whitelist()
def get_sales_order_by_id(id=None):
	"""
	Contoh: ambil daftar sales Order dari Accurate API
	"""
	settings = get_settings()

	# Step 1: cek host via /api-token.do (wajib untuk handle redirect 308)
	host = host_token()
	# Ambil host dari response
	
	# Step 2: request data ke host terbaru
	url = f"{host}/accurate/api/sales-order/list.do"
	headers = get_headers()
	res2 = requests.get(url, headers=headers, timeout=30)
	res2.raise_for_status()
	data_list =  res2.json()
	for row in data_list['d']:
	
		url_detail = f"{host}/accurate/api/sales-order/detail.do"
		headers = get_headers()
		res3 = requests.get(url_detail, headers=headers, timeout=30,params={'id':row['id']})
		res3.raise_for_status()
		return res3.json()

	