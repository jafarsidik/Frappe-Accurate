import frappe
from frappe.utils.background_jobs import enqueue
from frappe_accurate.api.auth import get_headers, get_settings, host_token
import requests
from frappe.utils import getdate
@frappe.whitelist(allow_guest=True)
def testing_sid():
	settings = get_settings()
	host = host_token()
	headers = get_headers()
	url = f"{host}/accurate/api/item/detail.do?id=13058"
	res = requests.get(url, headers=headers).json()
	return res

@frappe.whitelist()
def run_sync(docname):
	enqueue(
		method=sync_worker,
		queue="short",
		timeout=20000,
		docname=docname,
		now=False
	)
	return {"status": "queued"}

def sync_worker(docname):
	doc = frappe.get_doc("Accurate Settings", docname)

	# buat job list
	jobs = []
	for row in doc.table_mapping_accurate:
		if row.enable == 1:
			row_name = normalize_key(row.table_accurate)  # row tunggal untuk import/export
			jobs.append({"type": "import", "row": row, "row_name": row_name})
			jobs.append({"type": "export", "row": row, "row_name": row_name})

	# hitung total global
	global_total = 0
	for job in jobs:
		if job["type"] == "import":
			host = host_token()
			headers = get_headers()
			acc_table = job["row"].table_accurate
			res = requests.get(f"{host}/accurate/api/{acc_table}/list.do?page=1", headers=headers).json()
			global_total += int(res.get("sp", {}).get("rowCount", 0)) or 1
		else:
			global_total += frappe.db.count(job["row"].table_erp)

	global_done = 0

	# jalankan job satu per satu
	for job in jobs:
		send_table_progress(
			key=job["row_name"],
			type=job["type"],
			done=0,
			total=1,
			global_done=0,
			global_total=global_total
		)

		if job["type"] == "import":
			_, _, global_done = sync_from_accurate_table(
				job["row"], doc, frappe.session.user, global_done, global_total
			)
		else:
			_, _, global_done = sync_to_accurate_table(
				job["row"], frappe.session.user, global_done, global_total
			)

	send_table_progress(
		key="FINISHED",
		type=None,
		done=0,
		total=1,
		global_done=global_done,
		global_total=global_total
	)



def send_table_progress(key, type, done, total, global_done, global_total):
	done = min(done, total) if done is not None else 0
	frappe.publish_realtime(
		"sync_multi_progress",
		{
			"key": f"{key}-{type}" if type else key,  # row_name sama, type bedakan bar
			"done": done,
			"total": total or 1,
			"global_done": min(global_done, global_total),
			"global_total": global_total,
		},
		doctype="Accurate Settings",
		docname="Accurate Settings"
	)
def sync_from_accurate_table(row_mapping, settings, user, global_done, global_total):
	host = host_token()
	headers = get_headers()

	acc_table = row_mapping.table_accurate     # ex: vendor
	erp_table = row_mapping.table_erp          # ex: Supplier
	key = normalize_key(acc_table)

	# Ambil total data
	res = requests.get(f"{host}/accurate/api/{acc_table}/list.do?page=1", headers=headers).json()
	total_table = int(res.get("sp", {}).get("rowCount", 0)) or 1

	done_table = 0
	page = 1

	# =============================
	# Hardcode fallback mandatory
	# =============================
	DEFAULT_FALLBACK = {
		"Supplier": {
			"supplier_group": "All Supplier Groups",
			"supplier_type": "Company",
			"default_currency": "IDR",
			"default_price_list": "Standard Buying",
			"custom_supplier_category": "-",
			"custom_industry_type": "General",
		},
		"Customer": {
			"customer_group": "All Customer Groups",
			"customer_type": "Company",
			"industry": "Cosmetics",
			"custom_pic_customer": "Unknown"
		},
		
	}

	fallback = DEFAULT_FALLBACK.get(erp_table, {})

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

				# Ambil detail Accurate
				detail_url = f"{host}/accurate/api/{acc_table}/detail.do?id={acc_id}"
				detail = requests.get(detail_url, headers=headers).json()
				data_acc = detail.get("d", {})

				# =============================
				# HARDCORE MAPPING Field
				# =============================
				data_erp = {}

				if acc_table == "vendor" and erp_table == "Supplier":
					data_erp["supplier_name"] = data_acc.get("name")

				if acc_table == "customer" and erp_table == "Customer":
					data_erp['customer_name'] = data_acc.get("name")
					data_erp['custom_code_customer'] = data_acc.get("customerNo")
					data_erp['custom_customerno'] = data_acc.get("customerNo")

				if acc_table == "item-category" and erp_table == "Item Group":
					data_erp['item_group_name'] = data_acc.get("name")

				if acc_table == "unit" and erp_table == "UOM":
					data_erp['uom_name'] = data_acc.get("name")

				if acc_table == "item" and erp_table == "Item":
					item_category = data_acc.get("itemCategory") or {}
					data_erp['item_group'] = item_category.get("name")
					
					data_erp['custom_item_type_accurate'] = data_acc.get("itemType")
					#data_erp['item_code'] = data_acc.get("name")
					data_erp['item_code'] = data_acc.get("no")
					data_erp['stock_uom'] = data_acc.get("unit1Name")
					data_erp['custom_item_id_accurate'] = acc_id
				# =============================
				# PRIMARY KEY
				# =============================
				key_field_erp = row_mapping.key_id_field_table_erp
				key_field_acc = row_mapping.key_id_field_table_accurate

				key_value = data_acc.get(key_field_acc)
				if not key_value:
					frappe.log_error(f"Key missing: {key_field_acc}", f"[IMPORT SKIP] {acc_table}")
					continue

				data_erp[key_field_erp] = key_value

				# =============================
				# APPLY FALLBACK WAJIB
				# =============================
				for f, val in fallback.items():
					if f not in data_erp or data_erp[f] in (None, "", [], {}):
						data_erp[f] = val

				# =============================
				# INSERT / UPDATE
				# =============================
				
				if acc_table == "item" and erp_table == "Item":
					exists_item =  frappe.db.get_value(erp_table,data_acc.get("no"))
					if not exists_item:
						frappe.get_doc({"doctype": erp_table, **data_erp}).insert(ignore_permissions=True)
					else:
						frappe.db.set_value(erp_table, exists_item, data_erp)
				#Default
				else:
					exists = frappe.db.exists(erp_table, {key_field_erp: key_value})
					if not exists:
						
						frappe.get_doc({"doctype": erp_table, **data_erp}).insert(ignore_permissions=True)
					else:
						frappe.db.set_value(erp_table, exists, data_erp)

				frappe.db.commit()

				# =============================
				# PROGRESS
				# =============================
				done_table += 1
				global_done += 1
				send_table_progress(key, "import", done_table, total_table, global_done, global_total)

			except Exception:
				frappe.log_error(frappe.as_json(data_acc), f"[DEBUG DATA ERP] {acc_table} {acc_id}")
				frappe.log_error(frappe.get_traceback(), f"[ERROR IMPORT] {acc_table} {acc_id}")

		# Next page
		if page >= sp.get("pageCount", 1):
			break

		page += 1

	return done_table, total_table, global_done

def sync_to_accurate_table(row_mapping, user, global_done, global_total):
	host = host_token()
	headers = get_headers()

	acc_table = row_mapping.table_accurate      # contoh: vendor
	erp_table = row_mapping.table_erp           # contoh: Supplier
	key = normalize_key(acc_table)

	total_table = frappe.db.count(erp_table) or 1
	done_table = 0

	# =============================
	# Ambil seluruh data ERP
	# =============================
	erp_rows = frappe.get_all(erp_table, fields="*")

	# =============================
	# MAIN LOOP PER RECORD
	# =============================
	for row in erp_rows:
		try:
			payload = {}

			# ============================================================
			# MAPPING FIELD (ERP → ACCURATE)
			# Dibuat JELAS dengan komentar per mapping
			# ============================================================

			# ------------------------------------------------------------
			# SUPPLIER → vendor (Accurate)
			# ------------------------------------------------------------
			if erp_table == "Supplier" and acc_table == "vendor":

				# Accurate: name ← ERP: supplier_name
				payload["name"] = row.get("supplier_name")

				# Accurate: vendorNo ← ERP: supplier_code atau name
				payload["vendorNo"] = row.get("supplier_code") or row.get("name")

				# Accurate: taxId ← ERP: tax_id
				payload["taxId"] = row.get("tax_id")

				# Accurate: address ← ERP: address_display
				payload["address"] = row.get("address_display")

				# Accurate: isActive ← ERP: selalu True
				payload["isActive"] = True

			# ------------------------------------------------------------
			# CUSTOMER → customer (Accurate)
			# ------------------------------------------------------------
			if erp_table == "Customer" and acc_table == "customer":

				# Accurate: name ← ERP: customer_name
				payload["name"] = row.get("customer_name")

				# Accurate: customerNo ← ERP: custom_customerno atau name
				payload["customerNo"] = row.get("custom_customerno") or row.get("name")

				# Accurate: taxId ← ERP: tax_id
				payload["taxId"] = row.get("tax_id")

				# Accurate: address ← ERP: customer_primary_address
				payload["address"] = row.get("customer_primary_address")

				payload["isActive"] = True
				
			if erp_table == "Item Group" and acc_table == "item-category":
				payload['name'] = row.get("item_group_name")

			if erp_table == "UOM" and acc_table == "unit":
				payload['name'] = row.get("uom_name")

			if erp_table == "Item" and acc_table == "item":
				payload['itemCategoryName'] = row.get("item_group")
				payload['name'] = row.get("item_code")
				payload['no'] = row.get("item_code")
				payload['unit1Name'] = row.get("stock_uom")
				payload['itemType'] = "INVENTORY"

			# ============================================================
			# KEY ID untuk cek Accurate
			# ============================================================
			key_field_acc = row_mapping.key_id_field_table_accurate    # vendorNo / customerNo
			key_field_erp = row_mapping.key_id_field_table_erp         # supplier_code / customer_code

			key_value_acc = row.get(key_field_erp)

			# ============================================================
			# Cek apakah record sudah ada di Accurate
			# ============================================================
			exists_in_acc = False
			acc_id = None

			if key_value_acc:
				check_url = f"{host}/accurate/api/{acc_table}/view.do"
				res_check = requests.get(check_url, headers=headers, params={key_field_acc: key_value_acc}).json()

				exists_in_acc = res_check.get("s")
				if exists_in_acc:
					acc_id = res_check.get("r", {}).get("id")

			# ============================================================
			# UPDATE ke Accurate
			# ============================================================
			if exists_in_acc and acc_id:
				payload["id"] = acc_id
				save_url = f"{host}/accurate/api/{acc_table}/save.do"
				res_insert = requests.post(save_url, headers=headers, data=payload).json()

			# ============================================================
			# INSERT baru ke Accurate
			# ============================================================
			else:
				save_url = f"{host}/accurate/api/{acc_table}/save.do"
				res_insert = requests.post(save_url, headers=headers, data=payload).json()

				# Jika INSERT berhasil, simpan ID Accurate ke ERP
				acc_id_new = res_insert.get("r", {}).get("id")
				if acc_id_new:
					frappe.db.set_value(erp_table, row.name, key_field_erp, acc_id_new)
					frappe.db.commit()

			# ============================================================
			# Logging
			# ============================================================
			frappe.log_error(
				title=f"[SYNC EXPORT SUCCESS] {erp_table} → {acc_table}",
				message=frappe.as_json(res_insert)
			)

			# Update progress
			done_table += 1
			global_done += 1
			send_table_progress(key, "export", done_table, total_table, global_done, global_total)

		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"[SYNC EXPORT ERROR] {erp_table} → {acc_table}, row {row.name}"
			)

	return done_table, total_table, global_done



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

def normalize_key(name):
	return name.strip().lower().replace(" ", "-")
def normalize_item_payload(payload):
	# itemType wajib
	if "itemType" not in payload:
		payload["itemType"] = "INVENTORY"

	# unit wajib → harus object
	if "unit" in payload and isinstance(payload["unit"], str):
		payload["unit"] = {"name": payload["unit"]}

	# itemCategory wajib object
	if "itemCategory" in payload and isinstance(payload["itemCategory"], int):
		payload["itemCategory"] = {"id": payload["itemCategory"]}

	return payload

