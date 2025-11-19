import frappe
from frappe.utils.background_jobs import enqueue
from frappe_accurate.api.auth import get_headers, get_settings, host_token
import requests

@frappe.whitelist(allow_guest=True)
def testing_sid():
    settings = get_settings()
    host = host_token()
    headers = get_headers()
    url = f"{host}/accurate/api/item-category/detail.do?id=1"
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

    acc_table = row_mapping.table_accurate
    erp_table = row_mapping.table_erp
    key = normalize_key(acc_table)

    res = requests.get(f"{host}/accurate/api/{acc_table}/list.do?page=1", headers=headers).json()
    total_table = int(res.get("sp", {}).get("rowCount", 0)) or 1
    done_table = 0

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

                done_table += 1
                global_done += 1

                send_table_progress(key, "import", done_table, total_table, global_done, global_total)

            except Exception:
                frappe.log_error(frappe.get_traceback(), f"[SYNC IMPORT] Error {acc_table} {rec.get('id')}")

        if page >= sp.get("pageCount", 1):
            break
        page += 1

    return done_table, total_table, global_done


def sync_to_accurate_table(row_mapping, user, global_done, global_total):
    host = host_token()
    headers = get_headers()

    acc_table = row_mapping.table_accurate
    erp_table = row_mapping.table_erp
    key = normalize_key(acc_table)

    total_table = frappe.db.count(erp_table) or 1
    done_table = 0

    erp_data = frappe.get_all(
        erp_table,
        fields=["name"] + [row_mapping.get(f"field_erp_{i}") for i in range(1, 11) if row_mapping.get(f"field_erp_{i}")]
    )

    for row in erp_data:
        try:
            payload = {}
            for i in range(1, 11):
                erp_field = row_mapping.get(f"field_erp_{i}")
                acc_field = row_mapping.get(f"field_accurate_insert_{i}")
                if erp_field and acc_field:
                    payload[acc_field] = row.get(erp_field)

            key_field_acc = row_mapping.key_id_field_table_accurate
            key_field_erp = row_mapping.key_id_field_table_erp

            key_value_acc = row.get(key_field_erp)

            exists_in_acc = False
            acc_id = None
            if key_value_acc:
                check_url = f"{host}/accurate/api/{acc_table}/view.do"
                res_check = requests.get(check_url, headers=headers, params={key_field_acc: key_value_acc}).json()
                exists_in_acc = bool(res_check.get("s"))
                if exists_in_acc:
                    r = res_check.get("r", {})
                    acc_id = r.get("id") or r.get("no")

            if exists_in_acc and acc_id:
                payload["id"] = acc_id
                update_url = f"{host}/accurate/api/{acc_table}/save.do"
                requests.post(update_url, headers=headers, json=payload)
            else:
                insert_url = f"{host}/accurate/api/{acc_table}/save.do"
                res_insert = requests.post(insert_url, headers=headers, json=payload).json()
                r = res_insert.get("r", {})
                acc_id = r.get("id") or r.get("no")
                if acc_id:
                    frappe.db.set_value(erp_table, row.name, key_field_erp, acc_id)
                    frappe.db.commit()

            done_table += 1
            global_done += 1

            send_table_progress(key, "export", done_table, total_table, global_done, global_total)

        except Exception:
            frappe.log_error(frappe.get_traceback(), f"[SYNC EXPORT] Error {erp_table} → {acc_table} row {row.name}")

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
