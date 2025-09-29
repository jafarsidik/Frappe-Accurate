import frappe 
import requests
from frappe_accurate.api.auth import get_headers,get_settings,host_token
from frappe import _

@frappe.whitelist(allow_guest=True)
def sync_data(docname=None):
	"""
	Sinkronisasi dua arah dengan progress realtime
	"""
	settings = get_settings()

	# Step 1: Tarik data Accurate -> ERPNext
	frappe.publish_realtime(
		"sync_progress",
		{"step": 1, "msg": _("Sync dari Accurate ke ERPNext...")}
	)
	try:
		sync_from_accurate(settings)
		frappe.publish_realtime(
			"sync_progress",
			{"step": 1, "msg": _("✅ Sync dari Accurate ke ERPNext selesai")}
		)
	except Exception as e:
		frappe.publish_realtime(
			"sync_progress",
			{"step": 1, "msg": _("❌ Gagal sync dari Accurate: ") + str(e)}
		)
		frappe.throw(str(e))

	# Step 2: Push ERPNext -> Accurate
	frappe.publish_realtime(
		"sync_progress",
		{"step": 2, "msg": _("Sync dari ERPNext ke Accurate...")}
	)
	try:
		sync_to_accurate(settings)
		frappe.publish_realtime(
			"sync_progress",
			{"step": 2, "msg": _("✅ Sync dari ERPNext ke Accurate selesai")}
		)
	except Exception as e:
		frappe.publish_realtime(
			"sync_progress",
			{"step": 2, "msg": _("❌ Gagal sync ke Accurate: ") + str(e)}
		)
		frappe.throw(str(e))

	frappe.db.commit()

	return {"status": "success"}


def get_nested_value(data, field_path):
	"""
	Ambil nilai nested dari dict dengan path pakai titik.
	Contoh:
	  get_nested_value(detail['d'], "itemCategory.name")
	  -> "Category X"
	"""
	keys = field_path.split(".")
	for key in keys:
		if isinstance(data, dict):
			data = data.get(key)
		else:
			return None
	return data

# ---------------------------
# 1. Accurate -> ERPNext
# ---------------------------
def sync_from_accurate(settings=None):
	host = host_token()
	headers = get_headers()

	for row_mapping in settings.table_mapping_accurate:
		if not row_mapping.enable:  
			# nilai bisa 0/1 atau True/False
			continue
		acc_table = row_mapping.table_accurate
		erp_table = row_mapping.table_erp

		page = 1
		while True:
			url = f"{host}/accurate/api/{acc_table}/list.do?page={page}"
			res = requests.get(url, headers=headers).json()

			records = res['d']
			sp = res['sp']

			if not records:
				break

			for rec in records:
				acc_id = rec["id"]
				if not acc_id:
					continue
				# ambil detail per record
				detail_url = f"{host}/accurate/api/{acc_table}/detail.do?id={acc_id}"
				detail = requests.get(detail_url, headers=headers).json()
				data_erp = {}
				for i in range(1, 11):
					erp_field = row_mapping.get(f"field_erp_{i}")
					acc_field = row_mapping.get(f"field_accurate_{i}")
					if erp_field and acc_field:
						data_erp[erp_field] = get_nested_value(detail['d'], acc_field)
				
				# Gunakan field pertama sebagai key
				key_field_erp = row_mapping.key_id_field_table_erp        # misal "custom_item_code_accurate"
				key_field_acc = row_mapping.key_id_field_table_accurate  # misal "itemCode"

				# Ambil value langsung dari detail['d'] (atau nested jika perlu)
				key_value = get_nested_value(detail['d'], key_field_acc)
	
				if not key_value:
					frappe.log_error(f"[SKIP] {erp_table} record tanpa key ({key_field_acc}) → {detail['d']}")
					continue

				# Masukkan ke data_erp agar bisa insert/update
				data_erp[key_field_erp] = key_value

				exists = frappe.db.exists(erp_table, {key_field_erp: key_value})
				
				if not exists:
					try:
						frappe.get_doc({
							"doctype": erp_table,
							**data_erp
						}).insert(ignore_permissions=True)
						frappe.log_error(
							message=f"Insert {erp_table} {key_value} dari Accurate",
							title="[SYNC] Info"
						)
					except Exception:
						frappe.log_error(
							message=frappe.get_traceback(),
							title=f"[SYNC] Error insert {erp_table} {key_value}"
						)
				else:
					try:
						frappe.db.set_value(erp_table, exists, data_erp)
						frappe.log_error(
							message=f"Update {erp_table} {key_value} dari Accurate",
							title="[SYNC] Info"
						)
					except Exception:
						frappe.log_error(
							message=frappe.get_traceback(),
							title=f"[SYNC] Error update {erp_table} {key_value}"
						)


			# cek apakah masih ada page berikutnya
			if page >= sp["pageCount"]:
				break
			page += 1

# ---------------------------
# 2. ERPNext -> Accurate
# ---------------------------
def sync_to_accurate(settings):
	host = host_token()
	headers = get_headers()

	for row_mapping in settings.table_mapping_accurate:
		if not row_mapping.enable:  
			# nilai bisa 0/1 atau True/False
			continue
		acc_table = row_mapping.table_accurate
		erp_table = row_mapping.table_erp

		# Ambil data ERPNext
		erp_data = frappe.get_all(
			erp_table,
			fields=[
				row_mapping.get(f"field_erp_{i}") 
				for i in range(1, 11) 
				if row_mapping.get(f"field_erp_{i}")
			]
		)

		for row in erp_data:
			payload = {}
			for i in range(1, 10 + 1):
				erp_field = row_mapping.get(f"field_erp_{i}")
				acc_field = row_mapping.get(f"field_accurate_insert_{i}")
				if erp_field and acc_field:
					payload[acc_field] = row.get(erp_field)

			# Key pakai field Accurate khusus
			key_field = row_mapping.key_id_field_table_accurate
			key_value = payload.get(key_field)

			try:
				# ---------- Cek ke Accurate apakah sudah ada ----------
				page = 1
				exists = []
				while True:
					check_url = f"{host}/accurate/api/{acc_table}/list.do?page={page}"
					params = {"filter.field": key_field, "filter.value": key_value}
					res = requests.get(check_url, headers=headers, params=params).json()

					# Ambil data per halaman
					data_page = res.get("d", [])
					sp = res.get("sp", {})

					# Validasi ulang key_value
					for row_acc in data_page:
						if row_acc.get(key_field) == key_value:
							exists.append(row_acc)

					# Cek apakah masih ada page berikutnya
					if not sp or page >= sp.get("pageCount", 1):
						break
					page += 1

				if not exists:
					# -------- INSERT BARU --------
					insert_payload = {k: v for k, v in payload.items() if k != "id" and v is not None}
					insert_url = f"{host}/accurate/api/{acc_table}/save.do"
					res_insert = requests.post(insert_url, headers=headers, json=insert_payload).json()
					frappe.log_error(
						message=f"Insert {acc_table} {key_value} ke Accurate\nPayload: {insert_payload}\nRes: {res_insert}",
						title="[SYNC] Info Insert"
					)
				else:
					# -------- UPDATE DATA --------
					acc_id = exists[0].get("id")
					update_payload = {k: v for k, v in payload.items() if v is not None}
					update_payload["id"] = acc_id

					update_url = f"{host}/accurate/api/{acc_table}/save.do"
					res_update = requests.post(update_url, headers=headers, json=update_payload).json()
					frappe.log_error(
						message=f"Update {acc_table} {key_value} ke Accurate (ID: {acc_id})\nPayload: {update_payload}\nRes: {res_update}",
						title="[SYNC] Info Update"
					)

			except Exception:
				frappe.log_error(
					message=frappe.get_traceback(),
					title=f"[SYNC] Error sync {acc_table} {key_value}"
				)
