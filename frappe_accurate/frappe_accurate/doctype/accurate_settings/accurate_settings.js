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
        frappe.call({
            method: "frappe_accurate.api.syn.sync_to_accurate",  // ganti dengan path function Python tadi
            args: {
                docname: frm.doc.name
            },
            freeze: true,
            freeze_message: __("Processing sync..."),
            callback: function(r) {
                if (r.message && r.message.status === "success") {
                    frappe.msgprint({
                        title: __("Sync Complete"),
                        message: r.message.log.join("<br>"),
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
