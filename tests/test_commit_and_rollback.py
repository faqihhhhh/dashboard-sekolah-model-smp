import json
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from openpyxl import Workbook

from apps.accounts.models import Role
from apps.core.registry import get_spec
from apps.imports.commit import CommitBlocked, commit_preview
from apps.imports.engine import MappingConfig, run_dry_run
from apps.imports.models import ImportBatch, ImportBatchStatus, MappingProfile, ValueAlias
from apps.imports.readers import Table
from apps.imports.rollback import can_rollback, rollback_batch
from apps.referensi.models import AliasKabKota
from apps.sekolah.models import Sekolah

pytestmark = pytest.mark.django_db


def test_import_models_basic(make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)

    batch = ImportBatch.objects.create(
        dataset_key="sekolah",
        filename="test.xlsx",
        created_by=admin,
        total_rows=10,
    )
    assert batch.status == ImportBatchStatus.COMMITTED
    assert str(batch).startswith(f"Batch #{batch.pk}")

    profile = MappingProfile.objects.create(
        dataset_key="sekolah",
        nama="Profil Standar",
        header_signature=["NPSN", "Nama", "Kab/Kota"],
        config={"columns": {"NPSN": "npsn"}},
        created_by=admin,
    )
    assert profile.matches_headers(["NPSN", "Nama", "Kab/Kota"])
    assert not profile.matches_headers(["NPSN", "Nama"])

    alias = ValueAlias.objects.create(
        dataset_key="sekolah",
        field_name="pengusul",
        alias="Pemda",
        target_value="dinas",
        created_by=admin,
    )
    assert "pengusul" in str(alias)


def test_commit_create_sekolah(wilayah, make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)
    spec = get_spec("sekolah")

    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    rows = [
        headers,
        [
            "10101010",
            "SMP Negeri 1 Bandung",
            "Kota Bandung",
            "Negeri",
            "Dinas Pendidikan",
            "Pelaksana",
        ],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )
    preview = run_dry_run(spec, table, mapping)
    assert preview.ok
    assert preview.counts()["create"] == 1

    result = commit_preview(
        spec=spec,
        preview=preview,
        user=admin,
        filename="data.xlsx",
        mapping_config=mapping,
    )

    assert result.created == 1
    assert result.updated == 0
    assert result.batch is not None

    sekolah = Sekolah.objects.get(npsn="10101010")
    assert sekolah.nama == "SMP Negeri 1 Bandung"
    assert sekolah.import_batch == result.batch

    # Cek riwayat perubahan
    hist = sekolah.history.first()
    assert hist.history_user == admin
    assert f"Batch #{result.batch.pk}" in hist.history_change_reason


def test_commit_menyimpan_alias_kabkota_untuk_impor_berikutnya(wilayah, make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)
    spec = get_spec("sekolah")
    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    table = Table(
        name="Data",
        rows=[
            headers,
            ["10101012", "SMP Bogor", "Kab. Bogor", "Negeri", "Dinas Pendidikan", "Pelaksana"],
        ],
        n_cols=len(headers),
    )
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        },
        value_maps={"kabkota": {"Kab. Bogor": "Kabupaten Bogor"}},
    )
    preview = run_dry_run(spec, table, mapping)

    result = commit_preview(spec, preview, admin, filename="data.csv", mapping_config=mapping)

    alias = AliasKabKota.objects.get(alias="Kab. Bogor")
    assert alias.kabkota == wilayah.bogor
    assert result.created == 1


def test_commit_update_sekolah(wilayah, make_sekolah, make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)
    spec = get_spec("sekolah")

    # Sekolah awal di DB
    sekolah = make_sekolah(
        npsn="10101011",
        nama="SMP Awal",
        status="swasta",
        pengusul="mitra",
    )

    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    rows = [
        headers,
        ["10101011", "SMP Diubah", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )
    preview = run_dry_run(spec, table, mapping)
    assert preview.counts()["update"] == 1

    result = commit_preview(
        spec=spec,
        preview=preview,
        user=admin,
        filename="update.xlsx",
        mapping_config=mapping,
    )

    assert result.updated == 1
    sekolah.refresh_from_db()
    assert sekolah.nama == "SMP Diubah"
    assert sekolah.status == "negeri"
    assert sekolah.import_batch == result.batch

    # Pastikan catatan perubahan sebelumnya tercatat di change_log
    change_log = result.batch.change_log
    assert len(change_log["updated"]) == 1
    assert change_log["updated"][0]["pk"] == sekolah.pk
    assert change_log["updated"][0]["prev_fields"]["nama"] == "SMP Awal"
    assert change_log["updated"][0]["prev_fields"]["status"] == "swasta"


def test_commit_unchanged_sekolah(wilayah, make_sekolah, make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)
    spec = get_spec("sekolah")

    sekolah = make_sekolah(
        npsn="10101012",
        nama="SMP Tetap",
        status="negeri",
        pengusul="dinas",
        mapel_kka="pelaksana",
    )

    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    rows = [
        headers,
        ["10101012", "SMP Tetap", sekolah.kabkota.nama, "Negeri", "Dinas Pendidikan", "Pelaksana"],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )
    preview = run_dry_run(spec, table, mapping)
    assert preview.counts()["unchanged"] == 1

    result = commit_preview(spec=spec, preview=preview, user=admin, mapping_config=mapping)
    assert result.unchanged == 1
    assert result.created == 0
    assert result.updated == 0


def test_commit_error_membatalkan_seluruh_transaksi(wilayah, make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)
    spec = get_spec("sekolah")

    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    rows = [
        headers,
        ["10101013", "SMP Sah", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"],
        ["SALAH", "SMP Error", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )
    preview = run_dry_run(spec, table, mapping)
    assert preview.counts()["error"] == 1

    # Tanpa skip_errors -> transaksi gagal dan tidak ada data yang disimpan
    with pytest.raises(CommitBlocked):
        commit_preview(spec=spec, preview=preview, user=admin, skip_errors=False)

    assert not Sekolah.objects.filter(npsn="10101013").exists()
    assert ImportBatch.objects.count() == 0


def test_commit_dengan_skip_errors(wilayah, make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)
    spec = get_spec("sekolah")

    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    rows = [
        headers,
        ["10101014", "SMP Sah", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"],
        ["SALAH", "SMP Error", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )
    preview = run_dry_run(spec, table, mapping)
    assert preview.counts()["error"] == 1

    result = commit_preview(spec=spec, preview=preview, user=admin, skip_errors=True)
    assert result.created == 1
    assert result.skipped == 1
    assert Sekolah.objects.filter(npsn="10101014").exists()
    assert result.batch.skipped_count == 1


def test_commit_menyimpan_value_alias_dan_dipakai_di_dry_run_berikutnya(wilayah, make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)
    spec = get_spec("sekolah")

    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    rows = [
        headers,
        ["10101015", "SMP Uji Alias", "Kota Bandung", "Negeri", "Pemda Khusus", "Pelaksana"],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        },
        value_maps={"pengusul": {"Pemda Khusus": "dinas"}},
    )
    preview = run_dry_run(spec, table, mapping)
    assert preview.counts()["error"] == 0

    commit_preview(spec=spec, preview=preview, user=admin, mapping_config=mapping)

    # Verifikasi ValueAlias tersimpan di DB
    assert ValueAlias.objects.filter(
        dataset_key="sekolah",
        field_name="pengusul",
        alias="Pemda Khusus",
        target_value="dinas",
    ).exists()

    # Dry-run berikutnya TANPA value_maps eksplisit di mapping harus otomatis mengenali alias!
    mapping_tanpa_maps = MappingConfig(columns=mapping.columns)
    preview2 = run_dry_run(spec, table, mapping_tanpa_maps)
    assert preview2.counts()["error"] == 0
    assert preview2.rows[0].values["pengusul"] == "dinas"


def test_rollback_batch_milik_admin_sendiri(wilayah, make_sekolah, make_user):
    admin = make_user(email="admin@test.com", role=Role.ADMIN)
    spec = get_spec("sekolah")

    sekolah_lama = make_sekolah(
        npsn="10101016",
        nama="SMP Lama",
        status="swasta",
    )

    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    rows = [
        headers,
        # 1 dibuat baru
        ["10101017", "SMP Baru", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"],
        # 1 diperbarui
        ["10101016", "SMP Diubah", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )
    preview = run_dry_run(spec, table, mapping)
    result = commit_preview(spec=spec, preview=preview, user=admin, mapping_config=mapping)
    batch = result.batch

    assert Sekolah.objects.filter(npsn="10101017").exists()
    sekolah_lama.refresh_from_db()
    assert sekolah_lama.nama == "SMP Diubah"

    # Lakukan rollback
    rb_res = rollback_batch(batch, admin)
    assert rb_res["soft_deleted"] == 1
    assert rb_res["reverted"] == 1

    # Verifikasi data baru di-soft-delete
    assert not Sekolah.objects.filter(npsn="10101017").exists()
    sekolah_baru_terhapus = Sekolah.all_objects.get(npsn="10101017")
    assert sekolah_baru_terhapus.is_deleted
    assert sekolah_baru_terhapus.deleted_by == admin

    # Verifikasi data lama kembali ke nilai awal
    sekolah_lama.refresh_from_db()
    assert sekolah_lama.nama == "SMP Lama"
    assert sekolah_lama.status == "swasta"

    # Status batch berubah
    batch.refresh_from_db()
    assert batch.status == ImportBatchStatus.ROLLED_BACK
    assert batch.rolled_back_by == admin
    assert batch.rolled_back_at is not None

    # Rollback ulang harus ditolak
    with pytest.raises(ValueError, match="sudah dibatalkan"):
        rollback_batch(batch, admin)


def test_rollback_matriks_hak_akses(wilayah, make_user):
    admin1 = make_user(email="admin1@test.com", role=Role.ADMIN)
    admin2 = make_user(email="admin2@test.com", role=Role.ADMIN)
    super_admin = make_user(email="super@test.com", role=Role.SUPER_ADMIN)
    viewer = make_user(email="viewer@test.com", role=Role.VIEWER)

    batch = ImportBatch.objects.create(
        dataset_key="sekolah",
        filename="test.xlsx",
        created_by=admin1,
    )

    # Admin2 tidak boleh rollback batch milik Admin1
    ok, msg = can_rollback(batch, admin2)
    assert not ok
    assert "milik sendiri" in msg
    with pytest.raises(PermissionDenied):
        rollback_batch(batch, admin2)

    # Viewer tidak boleh
    ok, msg = can_rollback(batch, viewer)
    assert not ok
    with pytest.raises(PermissionDenied):
        rollback_batch(batch, viewer)

    # Super Admin BOLEH rollback batch milik siapa saja
    ok, _ = can_rollback(batch, super_admin)
    assert ok
    rollback_batch(batch, super_admin)
    assert batch.status == ImportBatchStatus.ROLLED_BACK


def test_management_commands_import_commit_dan_rollback(wilayah, make_user):
    admin = make_user(email="admin_cli@test.com", role=Role.ADMIN)

    # Siapkan file excel dan mapping
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"])
    ws.append(["10101018", "SMP CLI", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"])

    mapping_dict = {
        "columns": {
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        excel_path = Path(tmpdir) / "sekolah.xlsx"
        mapping_path = Path(tmpdir) / "mapping.json"
        wb.save(excel_path)
        mapping_path.write_text(json.dumps(mapping_dict), encoding="utf-8")

        out = StringIO()
        call_command(
            "import_commit",
            "sekolah",
            str(excel_path),
            "--mapping",
            str(mapping_path),
            "--user",
            admin.email,
            "--sheet",
            "Data",
            stdout=out,
        )
        assert "Commit berhasil" in out.getvalue()
        assert Sekolah.objects.filter(npsn="10101018").exists()

        batch = ImportBatch.objects.latest("pk")
        assert batch.created_count == 1

        # Uji import_rollback
        out_rb = StringIO()
        call_command("import_rollback", batch.pk, "--user", admin.email, stdout=out_rb)
        assert "Rollback Batch #" in out_rb.getvalue()
        assert not Sekolah.objects.filter(npsn="10101018").exists()
