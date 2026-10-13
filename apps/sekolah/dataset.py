from apps.core.registry import DatasetSpec, register

from .models import Sekolah

SEKOLAH = register(
    DatasetSpec(
        key="sekolah",
        label="Sekolah",
        model=Sekolah,
        url_namespace="sekolah",
        list_fields=(
            "npsn",
            "nama",
            "provinsi",
            "kabkota",
            "status",
            "pengusul",
            "mapel_kka",
            "jumlah_guru",
        ),
        # Yang boleh dilihat Guest (tanpa login). Selebihnya hanya untuk Viewer ke atas.
        public_fields=("npsn", "nama", "provinsi", "kabkota", "status", "pengusul", "mapel_kka"),
        form_fields=(
            "npsn",
            "nama",
            "jenjang",
            "provinsi",
            "kabkota",
            "status",
            "pengusul",
            "mapel_kka",
            "jumlah_guru",
        ),
        search_fields=("npsn", "nama"),
        filter_fields=("provinsi", "status", "pengusul", "mapel_kka"),
        natural_key=("npsn",),
        default_aliases={"pengusul": {"Pemda": "dinas", "Pemerintah Daerah": "dinas"}},
    )
)
