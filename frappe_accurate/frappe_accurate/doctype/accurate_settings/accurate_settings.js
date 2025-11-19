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
                 frappe.msgprint("Success Get Database");
                 window.location.reload()
            }
        });
    },
    syncronize_data_accurate(frm) {

       create_progress_container(frm);
        const body = $("#sync-progress-body");
        body.html("");

        let rows = {};

        frappe.realtime.on("sync_multi_progress", (data) => {

            if (data.key === "FINISHED") {
                frappe.show_alert("Sync selesai!");
                return;
            }

            //let key = data.key;
            let key = data.key.toLowerCase().replace(/\s+/g, '-');


            // Buat row baru jika belum ada
            if (!rows[key]) {

                let label = key.toUpperCase();

                let row = $(`
                    <div class="sync-row" id="row-${key}" style="margin-bottom: 12px;">
                        <div style="font-weight:600; margin-bottom:4px;">${label}</div>
                        <div id="counter-${key}" style="font-size:12px; color:#666;">0 / 0</div>

                        <div style="width:100%; height:12px; background:#eee; border-radius:6px;">
                            <div id="bar-${key}" 
                                style="height:12px; width:0%; 
                                        background:#1e90ff; border-radius:6px;
                                        transition: 0.25s;"></div>
                        </div>
                    </div>
                `);

                rows[key] = row;
                body.append(row);
            }

            let percent = data.total > 0 ? Math.min((data.done / data.total) * 100, 100) : 100;


            $(`#counter-${key}`).text(`${data.done} / ${data.total}`);
            $(`#bar-${key}`).css("width", percent + "%");

            if (percent >= 100) {
                $(`#bar-${key}`).css("background", "#2ecc71");
            }
        });

        // Mulai proses
        frappe.call({
            method: "frappe_accurate.api.syn_v2.run_sync",
            args: { docname: frm.doc.name },
            freeze: true,
            freeze_message: "Menjalankan sinkronisasi Accurate...",
            callback() {
                frappe.msgprint("Sinkronisasi dimulai…");
            }
        });

    }


    // syncronize_data_accurate(frm) {
    //     let progress_dialog = null;

    //     // Dengarkan event progress dari server
    //     frappe.realtime.on("sync_progress", (data) => {
    //         const phase = data.phase || __("Sinkronisasi");
    //         const progress = data.progress || 0;
    //         const msg = data.msg || "";

    //         if (!progress_dialog) {
    //             progress_dialog = frappe.show_progress(
    //                 phase,
    //                 progress,
    //                 100,
    //                 msg,
    //                 false
    //             );
    //         } else {
    //             frappe.show_progress(
    //                 phase,
    //                 progress,
    //                 100,
    //                 msg,
    //                 progress >= 100
    //             );
    //         }
    //     },"Accurate Settings", "Accurate Settings");

    //     // Jalankan proses sinkronisasi
    //     frappe.call({
    //         method: "frappe_accurate.api.syn.sync_data",
    //         args: { docname: frm.doc.name },
    //         freeze: true,
    //         freeze_message: __("Menjalankan sinkronisasi di background..."),
    //         callback: function (r) {
    //             if (r && r.message && r.message.status === "queued") {
    //                 frappe.msgprint({
    //                     title: __("Sinkronisasi Dimulai"),
    //                     message: __("Proses sinkronisasi berjalan di background. Progress akan tampil di layar."),
    //                     indicator: "blue",
    //                 });
    //             }
    //         },
    //         error: function (err) {
    //             frappe.msgprint({
    //                 title: __("Gagal"),
    //                 message: __("Terjadi kesalahan saat memulai sinkronisasi."),
    //                 indicator: "red",
    //             });
    //         },
    //     });
    // }

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

function create_progress_container(frm) {
    const container = frm.fields_dict.progress_syn_html.$wrapper;

    // Kosongkan isi container
    container.html(`
        <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
            <b>Progress Sinkronisasi</b>
        </div>
        <div id="sync-progress-body"></div>
    `);
}
