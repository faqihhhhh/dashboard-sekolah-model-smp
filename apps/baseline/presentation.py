"""Penyusun tampilan detail baseline per sekolah.

Mengubah daftar indikator Level 3 dan hasil rating satu sekolah menjadi struktur bertingkat
(kerangka → bagian A/B/C… → kelompok Level 2 → baris indikator) beserta ringkasan jumlah rating.
Modul ini tidak menghitung skor atau profil; hanya mengelompokkan dan menghitung agregat tampilan.
"""

from decimal import Decimal
from string import ascii_uppercase

from .models import Kerangka, RatingIndikator

# Rating → jumlah segmen terisi pada bar (1–4) dan nama warna di CSS (kelas ``bl-r-<warna>``).
RATING_LEVEL = {
    RatingIndikator.PRA_BERKEMBANG: 1,
    RatingIndikator.BERKEMBANG: 2,
    RatingIndikator.MAJU: 3,
    RatingIndikator.UNGGUL: 4,
}
RATING_TONE = {
    RatingIndikator.PRA_BERKEMBANG: "pra",
    RatingIndikator.BERKEMBANG: "berkembang",
    RatingIndikator.MAJU: "maju",
    RatingIndikator.UNGGUL: "unggul",
}
SEGMENT_COUNT = 4

# (kerangka, kode indikator Level 1) → (judul bagian, warna header, setengah lebar?)
SECTION_META = {
    (Kerangka.PM, "Murid"): ("Keunggulan Belajar Murid", "cyan", True),
    (Kerangka.PM, "Guru"): ("Keunggulan Mengajar Pendidik", "teal", True),
    (Kerangka.PM, "Kepala Satpen"): (
        "Keunggulan Mengajar Kepala Satuan Pendidikan",
        "navy",
        False,
    ),
    (Kerangka.KKA, "Murid"): ("Murid — Koding & Kecerdasan Artifisial", "cyan", False),
    (Kerangka.KKA, "Guru"): ("Guru — Koding & Kecerdasan Artifisial", "purple", False),
    (Kerangka.KKA, "Kepala Satpen"): (
        "Kepala Sekolah — Koding & Kecerdasan Artifisial",
        "blue",
        False,
    ),
}
FRAMEWORK_ORDER = (Kerangka.PM, Kerangka.KKA)


def _trim_zeros(value):
    """Buang nol di belakang koma khusus tampilan (2.40000 → 2.4); data tersimpan tak berubah."""
    if value is None:
        return None
    return Decimal(format(value.normalize(), "f"))


def _build_row(indicator, result, deleted):
    rating = result.rating if result else None
    if rating in RATING_LEVEL:
        level, tone, label = RATING_LEVEL[rating], RATING_TONE[rating], result.get_rating_display()
    elif result:
        level, tone, label = 0, "none", "Tidak terkategori"
    else:
        level, tone, label = 0, "empty", "Belum diisi"
    return {
        "indicator": indicator,
        "result": result,
        "deleted": deleted,
        "rating": rating,
        "level": level,
        "tone": tone,
        "label": label,
        "segments": [index < level for index in range(SEGMENT_COUNT)],
        "guides": list(indicator.panduan_rating.all()),
    }


def _build_summary(rows):
    counts = {value: 0 for value in RatingIndikator.values}
    uncategorized = missing = 0
    for row in rows:
        if row["rating"] in counts:
            counts[row["rating"]] += 1
        elif row["result"]:
            uncategorized += 1
        else:
            missing += 1
    legend = [
        {"label": label, "count": counts[value], "tone": RATING_TONE[value]}
        for value, label in RatingIndikator.choices
    ]
    if uncategorized:
        legend.append({"label": "Tidak terkategori", "count": uncategorized, "tone": "none"})
    if missing:
        legend.append({"label": "Belum diisi", "count": missing, "tone": "empty"})
    return legend, [item for item in legend if item["count"]]


def _build_sections(rows):
    """Kelompokkan baris satu kerangka menjadi bagian (Level 1) berisi kelompok (Level 2)."""
    sections = {}
    for row in rows:
        indicator = row["indicator"]
        level2 = indicator.parent
        level1 = level2.parent if level2 else None
        section_key = level1.pk if level1 else None
        section = sections.setdefault(
            section_key,
            {
                "level1": level1,
                "groups": {},
            },
        )
        group_key = level2.pk if level2 else None
        group = section["groups"].setdefault(group_key, {"level2": level2, "rows": []})
        group["rows"].append(row)

    ordered = sorted(
        sections.values(),
        key=lambda item: (
            (item["level1"].urutan, item["level1"].kode) if item["level1"] else (999, "")
        ),
    )
    for section in ordered:
        groups = sorted(
            section["groups"].values(),
            key=lambda item: (
                (item["level2"].urutan, item["level2"].kode) if item["level2"] else (999, "")
            ),
        )
        section["groups"] = [
            {
                "name": group["level2"].nama if group["level2"] else "Lainnya",
                "kode": group["level2"].kode if group["level2"] else "",
                "rows": group["rows"],
            }
            for group in groups
        ]
    return ordered


def build_detail_layout(baseline, indicators, results, all_results):
    """Susun blok PM dan KKA untuk halaman detail baseline.

    ``indicators``: indikator Level 3 aktif (sudah terurut, dengan parent dan panduan_rating).
    ``results``: ``{indikator_id: HasilIndikator}`` yang tidak terhapus.
    ``all_results``: sama, tetapi termasuk yang terhapus (soft delete).

    Indikator yang tidak punya rubrik rating **dan** tidak punya hasil (mis. indikator KKA Murid
    yang kolom ratingnya tidak ada di file sumber) tidak ditampilkan, selaras dengan donut
    dashboard yang hanya menghitung indikator berrubrik.
    """
    labels = dict(Kerangka.choices)
    letters = iter(ascii_uppercase)
    blocks = []
    for framework in FRAMEWORK_ORDER:
        rows = []
        for indicator in indicators:
            if indicator.kerangka != framework:
                continue
            result = results.get(indicator.pk)
            stored = all_results.get(indicator.pk)
            row = _build_row(indicator, result, bool(stored and stored.is_deleted))
            if row["guides"] or result:
                rows.append(row)

        legend, bar = _build_summary(rows)
        sections = []
        for section in _build_sections(rows):
            level1 = section["level1"]
            code = level1.kode if level1 else ""
            title, tone, half = SECTION_META.get(
                (framework, code), (level1.nama if level1 else "Lainnya", "navy", False)
            )
            sections.append(
                {
                    "letter": next(letters),
                    "title": title,
                    "tone": tone,
                    "half": half,
                    "groups": section["groups"],
                }
            )
        is_pm = framework == Kerangka.PM
        blocks.append(
            {
                "framework": framework,
                "label": labels[framework],
                "total": len(rows),
                "legend": legend,
                "bar": bar,
                "skor": _trim_zeros(baseline.skor_pm if is_pm else baseline.skor_kka),
                "profil": baseline.profil_pm if is_pm else baseline.profil_kka,
                "sections": sections,
            }
        )
    return blocks
