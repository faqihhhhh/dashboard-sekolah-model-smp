# Prototipe antarmuka (non-operasional)

Folder ini berisi prototipe React/Vite lama dengan data contoh statis. Folder ini tidak dijalankan oleh Django, tidak terhubung ke basis data, dan bukan frontend aplikasi yang dipakai.

Frontend operasional berada di template Django pada `templates/`, dengan aset lokal di `static/`. Ikuti `AGENT.md`: pertahankan render server Django + HTMX + Alpine.js; jangan menambah SPA/React. Fitur yang belum memiliki model Django tidak boleh diisi dengan data contoh seolah-olah data produksi.
