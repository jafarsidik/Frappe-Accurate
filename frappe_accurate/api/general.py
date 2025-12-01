import frappe
import requests
import hmac
import hashlib
import base64
from datetime import datetime
from frappe_accurate.api.auth import get_headers,get_settings,host_token

BASE_URL = "https://account.accurate.id/api"

@frappe.whitelist(allow_guest=True)
def get_database():
	
	host_url = f"{BASE_URL}/db-list.do"
	headers = get_headers()
	res = requests.get(host_url, headers=headers, timeout=30, allow_redirects=True)
	res.raise_for_status()
	data = res.json()
	settings = get_settings()
	# simpan session_id & db_id ke doctype
	settings.set("db_id", [])  # reset dulu kalau mau replace
	for row in data['d']:
		settings.append("db_id", {
			"id": row['id'],
			"alias": row['alias'],
			"licenseend": row['licenseEnd'],
			"sample": row['sample'],
			"demo": row['demo'],
			"trial": row['trial'],
			"expired": row['expired'],
		})
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	return settings

@frappe.whitelist()
def open_db(id=None): 
	"""
	Open database Accurate pakai API Token
	"""
	if not id:
		frappe.throw("Database ID is required")

	host_url = f"{BASE_URL}/open-db.do"
	headers = get_headers()

	# Kirim id sebagai form data
	res = requests.get(
		host_url,
		headers=headers,
		params={"id": id},
		timeout=30,
		allow_redirects=True
	)
	res.raise_for_status()
	data = res.json()

	# simpan informasi database aktif ke settings
	settings = get_settings()
	#settings.open_db = id  # pastikan ada field active_db di Accurate Settings
	#settings.host = data["d"]["host"] if "d" in data and "host" in data["d"] else None
	#settings.save(ignore_permissions=True)

	return data

@frappe.whitelist()
def db_detail(id=None): 
	"""
	database Detail Accurate pakai API Token
	"""
	if not id:
		frappe.throw("Database ID is required")

	host_url = f"{BASE_URL}/db-detail.do"
	headers = get_headers()

	# Kirim id sebagai form data
	res = requests.get(
		host_url,
		headers=headers,
		params={"id": id},
		timeout=30,
		allow_redirects=True
	)
	res.raise_for_status()
	data = res.json()

	# simpan informasi database aktif ke settings
	settings = get_settings()
	

	return data

@frappe.whitelist(allow_guest=True)
def send_accurate_unit():
    """
    Simpan Sales Order ke Accurate API
    Bisa dipanggil dari Frappe JS (frappe.call) atau Python
    """

    # Ambil host terbaru via /api-token.do
    host = host_token()
    url = f"{host}/accurate/api/unit/save.do"
    headers = get_headers()

    # Ambil data dari tabel 'UOM'
    data_post = frappe.db.get_list('UOM', fields=['name'])
    
    # Siapkan data untuk dikirim dalam format list of dicts
    data_post_send = [{"name": item['name']} for item in data_post]

    # Jika tidak ada data, lemparkan error
    if not data_post_send:
        frappe.throw("Tidak ada data yang dikirim ke Accurate")

   # Kirim setiap UOM satu per satu dalam loop
    responses = []
    for item in data_post_send:
        try:
            res = requests.post(url, headers=headers, json=item, timeout=30)  # Kirim satu per satu
            res.raise_for_status()  # Pastikan tidak ada error pada response
            responses.append(res.json())  # Simpan response dari API
        except requests.exceptions.RequestException as e:
            # Tangani error dari request
            responses.append({"error": str(e), "status": "error", "name": item['name']})

    # Kembalikan semua response API dalam format JSON
    return {"responses": responses}