import frappe
import requests
from frappe import _
from frappe_accurate.api.auth import get_headers, get_settings, host_token

@frappe.whitelist(allow_guest=True)
def testing():
	settings = get_settings()
	host = host_token()
	headers = get_headers()
	#url = f"{host}/accurate/api/item-category/list.do?page=2"
	url = f"{host}/accurate/api/item-category/detail.do?id=51"
	res = requests.get(url, headers=headers).json()
	return res
# ======================================================
# 🔹 ENTRY POINT (dipanggil dari JS)
# ======================================================
@frappe.whitelist()
def sync_data(docname=None):
	"""Entry point dari tombol, jalankan sync di background supaya tidak timeout."""
	user = frappe.session.user
	settings = get_settings()

	frappe.enqueue(
		"frappe_accurate.api.syn.run_sync", # python function or a module path as string
		queue="long", # one of short, default, long
		timeout=None, # pass timeout manually
		is_async=True, # if this is True, method is run in worker
		now=False, # if this is True, method is run directly (not in a worker) 
		job_name=None, # specify a job name
		#enqueue_after_commit=False, # enqueue the job after the database commit is done at the end of the request
		at_front=False, # put the job at the front of the queue
		#track_job=False, # tracks some metadata in `Background Task` doctype
		#**kwargs, # kwargs are passed to the method as arguments
		settings=settings,
		user=user,
	)
	


	return {"status": "queued", "message": "Sinkronisasi dijalankan di background"}


# ======================================================
# 🔹 PROSES UTAMA
# ======================================================
@frappe.whitelist()
def run_sync(settings, user):
	try:
		# === PHASE 1: Accurate → ERPNext ===
		frappe.publish_realtime(
			"sync_progress",
			{"phase": "Accurate → ERPNext", "progress": 0, "msg": _("Mengambil data dari Accurate...")},
			user=user,
			doctype="Accurate Settings",
			docname="Accurate Settings"
		)

		total_from, done_from = sync_from_accurate(settings, user)

		frappe.publish_realtime(
			"sync_progress",
			{
				"phase": "Accurate → ERPNext",
				"progress": 100,
				"msg": f"✅ Selesai sinkronisasi {done_from}/{total_from} data dari Accurate.",
			},
			user=user,
   			doctype="Accurate Settings",
			docname="Accurate Settings"
		)

		# === PHASE 2: ERPNext → Accurate ===
		frappe.publish_realtime(
			"sync_progress",
			{"phase": "ERPNext → Accurate", "progress": 0, "msg": _("Mengirim data ke Accurate...")},
			user=user,
   			doctype="Accurate Settings",
			docname="Accurate Settings"
		)

		total_to, done_to = sync_to_accurate(settings, user)

		frappe.publish_realtime(
			"sync_progress",
			{
				"phase": "ERPNext → Accurate",
				"progress": 100,
				"msg": f"✅ Selesai mengirim {done_to}/{total_to} data ke Accurate.",
			},
			user=user,
   			doctype="Accurate Settings",
			docname="Accurate Settings"
		)

		# === SELESAI ===
		frappe.publish_realtime(
			"sync_progress",
			{"phase": "Selesai", "progress": 100, "msg": _("🎉 Semua proses sinkronisasi selesai!")},
			user=user,
   			doctype="Accurate Settings",
			docname="Accurate Settings"
		)

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "SYNC ERROR")
		frappe.publish_realtime(
			"sync_progress",
			{"phase": "Error", "progress": 100, "msg": f"❌ Terjadi kesalahan: {e}"},
			user=user,
   			doctype="Accurate Settings",
			docname="Accurate Settings"
		)


# ======================================================
# 🔹 ACCURATE → ERPNext
# ======================================================
def sync_from_accurate(settings, user):
	settings = get_settings()
	host = host_token()
	headers = get_headers()

	total_records = 0
	done_records = 0

	# Hitung total record dari semua tabel aktif
	for row_mapping in settings.table_mapping_accurate:
		if not row_mapping.enable:
			continue
		acc_table = row_mapping.table_accurate
		url = f"{host}/accurate/api/{acc_table}/list.do?page=1"
		res = requests.get(url, headers=headers).json()
		#return res
		sp = res.get("sp", {})
		total_records += int(sp.get("rowCount", 0))

	# Loop tabel Accurate yang aktif
	for row_mapping in settings.table_mapping_accurate:
		if not row_mapping.enable:
			continue

		acc_table = row_mapping.table_accurate
		erp_table = row_mapping.table_erp

		page = 1
		while True:
			url = f"{host}/accurate/api/{acc_table}/list.do?page={page}&pageSize=1000"
			res = requests.get(url, headers=headers).json()
			records = res.get("d", [])
			sp = res.get("sp", {})

			if not records:
				break

			for rec in records:
				try:
					acc_id = rec.get("id")
					if not acc_id:
						continue

					detail_url = f"{host}/accurate/api/{acc_table}/detail.do?id={acc_id}"
					detail = requests.get(detail_url, headers=headers).json()

					data_erp = {}
					for i in range(1, 11):
						erp_field = row_mapping.get(f"field_erp_{i}")
						acc_field = row_mapping.get(f"field_accurate_{i}")
						if erp_field and acc_field:
							data_erp[erp_field] = get_nested_value(detail.get("d", {}), acc_field)

					key_field_erp = row_mapping.key_id_field_table_erp
					key_field_acc = row_mapping.key_id_field_table_accurate
					key_value = get_nested_value(detail.get("d", {}), key_field_acc)

					if not key_value:
						continue

					data_erp[key_field_erp] = key_value
					exists = frappe.db.exists(erp_table, {key_field_erp: key_value})

					if not exists:
						frappe.get_doc({"doctype": erp_table, **data_erp}).insert(ignore_permissions=True)
					else:
						frappe.db.set_value(erp_table, exists, data_erp)
					frappe.db.commit()
					done_records += 1
					progress = int((done_records / total_records) * 100)
					frappe.publish_realtime(
						"sync_progress",
						{
							"phase": "Accurate → ERPNext",
							"progress": progress,
							"msg": f"Memproses {done_records}/{total_records} data dari Accurate...",
						},
						user=user,
						doctype="Accurate Settings",
						docname="Accurate Settings"
	  
					)

					if done_records % 20 == 0:
						frappe.db.commit()

				except Exception:
					frappe.log_error(frappe.get_traceback(), f"[SYNC] Error {acc_table} {rec.get('id')}")

			if page >= sp.get("pageCount", 1):
				break
			page += 1

	
	return total_records, done_records


# ======================================================
# 🔹 ERPNext → Accurate
# ======================================================
def sync_to_accurate(settings, user):
	host = host_token()
	headers = get_headers()

	total_records = 0
	done_records = 0

	for row_mapping in settings.table_mapping_accurate:
		if not row_mapping.enable:
			continue
		erp_table = row_mapping.table_erp
		total_records += frappe.db.count(erp_table)

	for row_mapping in settings.table_mapping_accurate:
		if not row_mapping.enable:
			continue

		acc_table = row_mapping.table_accurate
		erp_table = row_mapping.table_erp
		custom_item_code_accurate = row_mapping.field_erp_4

		erp_data = frappe.get_all(
			erp_table,
			fields=["name"]
			+ [
				row_mapping.get(f"field_erp_{i}")
				for i in range(1, 11)
				if row_mapping.get(f"field_erp_{i}")
			],
		)

		for row in erp_data:
			payload = {}
			for i in range(1, 11):
				erp_field = row_mapping.get(f"field_erp_{i}")
				acc_field = row_mapping.get(f"field_accurate_insert_{i}")
				if erp_field and acc_field:
					payload[acc_field] = row.get(erp_field)

			key_field = row_mapping.key_id_field_table_accurate
			key_value = payload.get(key_field)
			if not key_value:
				continue

			try:
				detail_url = f"{host}/accurate/api/{acc_table}/view.do"
				params = {key_field: key_value}
				res_check = requests.get(detail_url, headers=headers, params=params).json()

				if res_check.get("s"):
					acc_id = res_check.get("r", {}).get("id") or res_check.get("r", {}).get("no")
					update_payload = payload.copy()
					update_payload["id"] = acc_id
					update_url = f"{host}/accurate/api/{acc_table}/save.do"
					requests.post(update_url, headers=headers, json=update_payload)
					frappe.db.set_value(erp_table, row.name, custom_item_code_accurate, acc_id)
				else:
					insert_url = f"{host}/accurate/api/{acc_table}/save.do"
					res_insert = requests.post(insert_url, headers=headers, json=payload).json()
					acc_id = res_insert.get("r", {}).get("id") or res_insert.get("r", {}).get("no")
					if acc_id:
						frappe.db.set_value(erp_table, row.name, custom_item_code_accurate, acc_id)

				done_records += 1
				progress = int((done_records / total_records) * 100)
				frappe.publish_realtime(
					"sync_progress",
					{
						"phase": "ERPNext → Accurate",
						"progress": progress,
						"msg": f"Mengirim {done_records}/{total_records} data ke Accurate...",
					},
					user=user,
					doctype="Accurate Settings",
					docname="Accurate Settings"
				)

				if done_records % 20 == 0:
					frappe.db.commit()

			except Exception:
				frappe.log_error(frappe.get_traceback(), f"[SYNC] Error sync {acc_table} {key_value}")

	frappe.db.commit()
	return total_records, done_records


# ======================================================
# 🔹 UTILITAS
# ======================================================
def get_nested_value(data, field_path):
	keys = field_path.split(".")
	for key in keys:
		if isinstance(data, dict):
			data = data.get(key)
		else:
			return None
	return data
