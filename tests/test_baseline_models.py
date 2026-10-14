from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.baseline.importing import (
    BaselineCommitBlocked,
    BaselineMapping,
    commit_baseline_preview,
    run_baseline_dry_run,
    transform_indicator_values,
)
from apps.baseline.models import (
    HasilBaseline,
    HasilIndikator,
    KamusIndikator,
    Kerangka,
    LevelIndikator,
    PanduanRating,
    RatingIndikator,
)
from apps.imports.readers import Table
from apps.imports.rollback import rollback_batch
from apps.referensi.models import Periode

pytestmark = pytest.mark.django_db


def test_hasil_baseline_menyimpan_skor_profil_apa_adanya(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Awal", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    result = HasilBaseline.objects.create(
        sekolah=school,
        periode=period,
        skor_pm=Decimal("73.2500"),
        profil_pm="Berkembang",
        profil_data={"kode_contoh": "nilai sumber"},
    )

    assert result.skor_pm == Decimal("73.2500")
    assert result.skor_kka is None
    assert result.profil_data == {"kode_contoh": "nilai sumber"}
    assert result.history.count() == 1


def test_hasil_baseline_mempertahankan_presisi_skor(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Presisi", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    result = HasilBaseline.objects.create(
        sekolah=school, periode=period, skor_pm=Decimal("2.3552083333")
    )

    result.refresh_from_db()
    assert result.skor_pm == Decimal("2.3552083333")


def test_hasil_baseline_unik_per_sekolah_dan_periode(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Unik", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    HasilBaseline.objects.create(sekolah=school, periode=period)

    with pytest.raises(IntegrityError), transaction.atomic():
        HasilBaseline.objects.create(sekolah=school, periode=period)


def test_hasil_indikator_rating_dan_indikator_tidak_ganda(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Indikator", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    baseline = HasilBaseline.objects.create(sekolah=school, periode=period)
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
        deskripsi="Panduan yang disediakan pemilik program.",
    )
    result = HasilIndikator.objects.create(
        hasil_baseline=baseline,
        indikator=indicator,
        rating=RatingIndikator.PRA_BERKEMBANG,
    )

    assert result.get_rating_display() == "Pra-Berkembang"
    assert result.history.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        HasilIndikator.objects.create(hasil_baseline=baseline, indikator=indicator)

    result.rating = "rating-tidak-valid"
    with pytest.raises(ValidationError):
        result.full_clean()


def test_kamus_mengharuskan_induk_sesuai_level_dan_kerangka():
    parent = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L1,
        kode="murid",
        nama="Murid",
    )
    child = KamusIndikator(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L2,
        kode="1.1",
        nama="Contoh",
        parent=parent,
    )
    child.full_clean()

    child.parent = None
    with pytest.raises(ValidationError):
        child.full_clean()

    child.parent = KamusIndikator.objects.create(
        kerangka=Kerangka.KKA,
        level=LevelIndikator.L1,
        kode="guru-kka",
        nama="Guru",
    )
    with pytest.raises(ValidationError):
        child.full_clean()


def test_seed_baseline_reference_idempoten():
    call_command("seed_baseline_reference", verbosity=0)
    assert KamusIndikator.objects.count() == 56
    assert PanduanRating.objects.count() == 136
    level_three_count = KamusIndikator.objects.filter(
        level=LevelIndikator.L3, parent__isnull=False
    ).count()
    assert level_three_count == 35

    call_command("seed_baseline_reference", verbosity=0)
    assert KamusIndikator.objects.count() == 56
    assert PanduanRating.objects.count() == 136


def test_transformasi_rating_lebar_ke_panjang_mengabaikan_kosong():
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
    )

    transformed = transform_indicator_values(
        {"PM | 1.1.1": "Pra- Berkembang", "PM | 1.1.2": "#N/A"},
        {"PM | 1.1.1": indicator},
    )

    assert transformed.ok
    assert len(transformed.values) == 1
    assert transformed.values[0].indikator == indicator
    assert transformed.values[0].rating == RatingIndikator.PRA_BERKEMBANG


def test_transformasi_rating_melaporkan_nilai_tidak_dikenal():
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.KKA,
        level=LevelIndikator.L3,
        kode="2.1.1",
        nama="Contoh indikator",
    )

    transformed = transform_indicator_values(
        {"KKA | 2.1.1": "Kategori baru"}, {"KKA | 2.1.1": indicator}
    )

    assert not transformed.ok
    assert transformed.values == []
    assert len(transformed.issues) == 1


def test_transformasi_rating_menolak_pemetaan_ganda():
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
    )

    transformed = transform_indicator_values(
        {"PM | 1.1.1": "Maju", "Salinan": "Maju"},
        {"PM | 1.1.1": indicator, "Salinan": indicator},
    )

    assert not transformed.ok
    assert len(transformed.mapping_errors) == 1


def test_dry_run_baseline_valid_tidak_menulis_data(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Dry Run", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
    )
    table = Table(
        name="SMP",
        rows=[
            ["NPSN", "Skor PM", "Profil PM", "Kondisi", "PM | 1.1.1"],
            [school.npsn, "2.3552083333", "Berkembang", "Tersedia", "Maju"],
        ],
        n_cols=5,
    )
    mapping = BaselineMapping(
        npsn_header="NPSN",
        summary_columns={"skor_pm": "Skor PM", "profil_pm": "Profil PM"},
        profile_columns={"Kondisi": "kondisi"},
        indicator_columns={"PM | 1.1.1": indicator},
    )

    preview = run_baseline_dry_run(table, periode=period, mapping=mapping)

    assert preview.ok
    assert preview.counts() == {"create": 1, "update": 0, "unchanged": 0, "error": 0}
    assert preview.rows[0].school == school
    assert preview.rows[0].values["skor_pm"] == Decimal("2.3552083333")
    assert preview.rows[0].values["profil_pm"] == "Berkembang"
    assert preview.rows[0].indicators[0].rating == RatingIndikator.MAJU
    assert HasilBaseline.objects.count() == 0
    assert HasilIndikator.objects.count() == 0


def test_dry_run_baseline_melaporkan_npsn_ganda_dan_rating_tidak_dikenal(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Validasi", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
    )
    table = Table(
        name="SMP",
        rows=[
            ["NPSN", "PM | 1.1.1"],
            [school.npsn, "Rating baru"],
            [school.npsn, "Maju"],
        ],
        n_cols=2,
    )

    preview = run_baseline_dry_run(
        table,
        periode=period,
        mapping=BaselineMapping(npsn_header="NPSN", indicator_columns={"PM | 1.1.1": indicator}),
    )

    assert not preview.ok
    assert preview.counts()["error"] == 2
    assert len(preview.rows[0].issues) == 1
    assert len(preview.rows[1].issues) == 1


def test_dry_run_baseline_mengabaikan_kolom_kosong_saat_pembaruan(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Tidak Menimpa Kosong", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
    )
    baseline = HasilBaseline.objects.create(
        sekolah=school,
        periode=period,
        skor_pm=Decimal("2.5"),
        profil_data={"kondisi": "Tersedia"},
    )
    HasilIndikator.objects.create(
        hasil_baseline=baseline, indikator=indicator, rating=RatingIndikator.MAJU
    )
    table = Table(
        name="SMP",
        rows=[["NPSN", "Skor PM", "Kondisi", "PM | 1.1.1"], [school.npsn, None, None, None]],
        n_cols=4,
    )

    preview = run_baseline_dry_run(
        table,
        periode=period,
        mapping=BaselineMapping(
            npsn_header="NPSN",
            summary_columns={"skor_pm": "Skor PM"},
            profile_columns={"Kondisi": "kondisi"},
            indicator_columns={"PM | 1.1.1": indicator},
        ),
    )

    assert preview.ok
    assert preview.counts()["unchanged"] == 1
    assert preview.rows[0].values == {}
    assert preview.rows[0].indicators == []


def test_commit_baseline_menyimpan_ringkasan_rating_dan_batch(make_sekolah, make_user):
    school = make_sekolah()
    user = make_user("admin")
    period = Periode.objects.create(
        nama="Baseline Commit", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
    )
    table = Table(
        name="SMP",
        rows=[["NPSN", "Skor PM", "PM | 1.1.1"], [school.npsn, "2.5", "Maju"]],
        n_cols=3,
    )
    mapping = BaselineMapping(
        npsn_header="NPSN",
        summary_columns={"skor_pm": "Skor PM"},
        indicator_columns={"PM | 1.1.1": indicator},
    )
    preview = run_baseline_dry_run(table, periode=period, mapping=mapping)

    result = commit_baseline_preview(
        preview, periode=period, mapping=mapping, user=user, filename="baseline.xlsx"
    )

    baseline = HasilBaseline.objects.get(sekolah=school, periode=period)
    rating = HasilIndikator.objects.get(hasil_baseline=baseline, indikator=indicator)
    assert result.created == 1
    assert result.batch.dataset_key == "baseline"
    assert result.batch.created_by == user
    assert baseline.import_batch == result.batch
    assert rating.rating == RatingIndikator.MAJU
    assert rating.import_batch == result.batch
    assert baseline.history.first().history_user == user

    rolled_back = rollback_batch(result.batch, user)
    baseline.refresh_from_db()
    rating.refresh_from_db()
    assert rolled_back["soft_deleted"] == 2
    assert baseline.is_deleted
    assert rating.is_deleted


def test_rollback_batch_baseline_memulihkan_perubahan(make_sekolah, make_user):
    school = make_sekolah()
    user = make_user("admin")
    period = Periode.objects.create(
        nama="Baseline Pulihkan Perubahan", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
    )
    baseline = HasilBaseline.objects.create(
        sekolah=school,
        periode=period,
        skor_pm=Decimal("2.5"),
        profil_data={"catatan": "awal"},
    )
    rating = HasilIndikator.objects.create(
        hasil_baseline=baseline, indikator=indicator, rating=RatingIndikator.MAJU
    )
    table = Table(
        name="SMP",
        rows=[
            ["NPSN", "Skor PM", "Catatan", "PM | 1.1.1"],
            [school.npsn, "3.5", "baru", "Unggul"],
        ],
        n_cols=4,
    )
    mapping = BaselineMapping(
        npsn_header="NPSN",
        summary_columns={"skor_pm": "Skor PM"},
        profile_columns={"Catatan": "catatan"},
        indicator_columns={"PM | 1.1.1": indicator},
    )
    preview = run_baseline_dry_run(table, periode=period, mapping=mapping)
    committed = commit_baseline_preview(
        preview, periode=period, mapping=mapping, user=user, filename="baseline-update.xlsx"
    )

    assert committed.updated == 1
    baseline.refresh_from_db()
    rating.refresh_from_db()
    assert baseline.skor_pm == Decimal("3.5")
    assert baseline.profil_data["catatan"] == "baru"
    assert rating.rating == RatingIndikator.UNGGUL

    result = rollback_batch(committed.batch, user)
    baseline.refresh_from_db()
    rating.refresh_from_db()
    assert result["reverted"] == 2
    assert baseline.skor_pm == Decimal("2.5")
    assert baseline.profil_data == {"catatan": "awal"}
    assert rating.rating == RatingIndikator.MAJU


def test_commit_baseline_membatalkan_semua_jika_preview_error(make_sekolah, make_user):
    school = make_sekolah()
    user = make_user("admin")
    period = Periode.objects.create(
        nama="Baseline Commit Gagal", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    table = Table(
        name="SMP",
        rows=[["NPSN", "Profil PM"], [school.npsn, "Nilai"], ["buruk", "Nilai"]],
        n_cols=2,
    )
    mapping = BaselineMapping(npsn_header="NPSN", summary_columns={"profil_pm": "Profil PM"})
    preview = run_baseline_dry_run(table, periode=period, mapping=mapping)

    with pytest.raises(BaselineCommitBlocked):
        commit_baseline_preview(preview, periode=period, mapping=mapping, user=user)

    assert HasilBaseline.objects.count() == 0
