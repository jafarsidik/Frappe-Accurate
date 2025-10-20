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
    syncronize_data_accurate(frm) {
        let progress_dialog = null;

        // Dengarkan event progress dari server
        frappe.realtime.on("sync_progress", (data) => {
            const phase = data.phase || __("Sinkronisasi");
            const progress = data.progress || 0;
            const msg = data.msg || "";

            if (!progress_dialog) {
                progress_dialog = frappe.show_progress(
                    phase,
                    progress,
                    100,
                    msg,
                    false
                );
            } else {
                frappe.show_progress(
                    phase,
                    progress,
                    100,
                    msg,
                    progress >= 100
                );
            }
        },"Accurate Settings", "Accurate Settings");

        // Jalankan proses sinkronisasi
        frappe.call({
            method: "frappe_accurate.api.syn.sync_data",
            args: { docname: frm.doc.name },
            freeze: true,
            freeze_message: __("Menjalankan sinkronisasi di background..."),
            callback: function (r) {
                if (r && r.message && r.message.status === "queued") {
                    frappe.msgprint({
                        title: __("Sinkronisasi Dimulai"),
                        message: __("Proses sinkronisasi berjalan di background. Progress akan tampil di layar."),
                        indicator: "blue",
                    });
                }
            },
            error: function (err) {
                frappe.msgprint({
                    title: __("Gagal"),
                    message: __("Terjadi kesalahan saat memulai sinkronisasi."),
                    indicator: "red",
                });
            },
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
