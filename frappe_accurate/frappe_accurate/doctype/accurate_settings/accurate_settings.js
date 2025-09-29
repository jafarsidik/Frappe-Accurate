// Copyright (c) 2025, Jafar Sidik and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accurate Settings", {
// 	refresh(frm) {

// 	},
    get_database_accurate_by_api_token(frm){
        // Step 1: Minta URL authorize
        frappe.call({
            method: "frappe_accurate.api.general.get_database",
            callback: function(r) {
                alert("Success")
                 window.location.reload()
            }
        });
    },
    syncronize_data_accurate(frm){
        let total_steps = 2; // jumlah step sync
        let current_step = 0;

        // listener untuk update progress realtime
        frappe.realtime.on("sync_progress", (data) => {
            current_step = data.step;
            frappe.show_progress(
                __("Sync Progress"),
                current_step,
                total_steps,
                data.msg,
                current_step === total_steps // auto hide kalau sudah selesai
            );
        });

        frappe.call({
            method: "frappe_accurate.api.syn.sync_data",
            args: { docname: frm.doc.name },
            freeze: true,
            freeze_message: __("Starting sync..."),
            callback: function (r) {
                if (r.message && r.message.status === "success") {
                    frappe.msgprint({
                        title: __("Sync Complete"),
                        message: __("Sinkronisasi berhasil diselesaikan."),
                        indicator: "green"
                    });
                    frm.reload_doc();
                } else {
                    frappe.msgprint({
                        title: __("Error"),
                        message: __("Sync failed"),
                        indicator: "red"
                    });
                }
            }
        });
    }
    
});
frappe.ui.form.on("DB ID Accurate", {
// 	refresh(frm) {

// 	},
    open_db(frm, cdt, cdn){
       const row = locals[cdt][cdn]
        // Step 1: Minta URL authorize
        frappe.call({
            method: "frappe_accurate.api.general.open_db",
            args: {
                id: row.id
            },
            callback: function(r) {
                console.log(r)
               alert("Success")
        //          window.location.reload()
            }
        });
        alert(row.id)
    }
});
