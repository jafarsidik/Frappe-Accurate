import frappe
import requests
from frappe_accurate.api.auth import get_headers,get_settings,host_token

@frappe.whitelist()
def sync_data(docname=None):
	"""
	Sinkronisasi dua arah:
	- Dari Accurate -> ERPNext
	- Dari ERPNext -> Accurate
	"""
	settings = get_settings()

	# Tarik data dari Accurate
	sync_from_accurate(settings)

	# Push data dari ERPNext
	sync_to_accurate(settings)

	frappe.db.commit()
	#return "Sync selesai (2 arah)"


# ---------------------------
# 1. Accurate -> ERPNext
# ---------------------------
def sync_from_accurate(settings):
	host = host_token()
	headers = get_headers()

	for row_mapping in settings.table_mapping_accurate:
		acc_table = row_mapping.table_accurate
		erp_table = row_mapping.table_erp

		url = f"{host}/accurate/api/{acc_table}/list.do"
		res = requests.get(url, headers=headers).json()
		records = res
		return records
		"""
		for rec in records:
			data_erp = {}
			for i in range(1, 11):
				erp_field = row_mapping.get(f"field_erp_{i}")
				acc_field = row_mapping.get(f"field_accurate_{i}")
				if erp_field and acc_field:
					data_erp[erp_field] = rec.get(acc_field)

			# Gunakan field pertama sebagai key
			key_field = row_mapping.get("key_id_field_table_erp")
			key_value = data_erp.get(key_field)
			if not key_field or not key_value:
				continue

			exists = frappe.db.exists(erp_table, {key_field: key_value})

			if not exists:
				frappe.get_doc({ "doctype": erp_table, **data_erp }).insert(ignore_permissions=True)
				frappe.logger().info(f"[SYNC] Insert {erp_table} {key_value} dari Accurate")
			else:
				frappe.db.set_value(erp_table, exists, data_erp)
				frappe.logger().info(f"[SYNC] Update {erp_table} {key_value} dari Accurate")
		"""

# ---------------------------
# 2. ERPNext -> Accurate
# ---------------------------
def sync_to_accurate(settings):
	host = host_token()
	headers = get_headers()

	for row_mapping in settings.table_mapping_accurate:
		acc_table = row_mapping.table_accurate
		erp_table = row_mapping.table_erp

		# Ambil data ERPNext
		erp_data = frappe.get_all(
			erp_table,
			fields=[row_mapping.get(f"field_erp_{i}") for i in range(1, 11) if row_mapping.get(f"field_erp_{i}")]
		)

		for row in erp_data:
			payload = {}
			for i in range(1, 11):
				erp_field = row_mapping.get(f"field_erp_{i}")
				acc_field = row_mapping.get(f"field_accurate_{i}")
				if erp_field and acc_field:
					payload[acc_field] = row.get(erp_field)

			# Key pakai field Accurate pertama
			key_field = row_mapping.get("key_id_field_table_accurate")
			key_value = payload.get(key_field)
			if not key_field or not key_value:
				continue

			# Cek ke Accurate apakah sudah ada
			check_url = f"{host}/accurate/api/{acc_table}/list.do"
			params = {"filter.field": key_field, "filter.value": key_value}
			res = requests.get(check_url, headers=headers, params=params).json()
			exists = res.get("d", [])

			if not exists:
				# Insert baru ke Accurate
				insert_url = f"{host}/accurate/api/{acc_table}/save.do"
				res_insert = requests.post(insert_url, headers=headers, json=payload).json()
				frappe.logger().info(f"[SYNC] Insert {acc_table} {key_value} ke Accurate: {res_insert}")
			else:
				# Update data ke Accurate
				record_id = exists[0].get("id")
				update_url = f"{host}/accurate/api/{acc_table}/save.do?id={record_id}"
				res_update = requests.post(update_url, headers=headers, json=payload).json()
				frappe.logger().info(f"[SYNC] Update {acc_table} {key_value} ke Accurate: {res_update}")


# ---------------------------
# Helper Functions
# ---------------------------
# def get_settings():
#     return frappe.get_single("Accurate Setting")

# def host_token():
#     """Ambil host Accurate terbaru via API /api-token.do"""
#     return "https://account.accurate.id"

# def get_headers():
#     return {
#         "Authorization": f"Bearer {frappe.db.get_single_value('Accurate Setting', 'access_token')}",
#         "Content-Type": "application/json"
#     }
