"""Tes normalisasi. Tidak butuh database: model wilayah ditiru (stub) agar logika pencocokan
bisa diuji sendirian. Pencocokan terhadap data wilayah sungguhan diuji di test_import_commit.py.
"""

import sys
import types
import unittest
from unittest import mock

from apps.imports.normalize import (
    ChoiceResolver,
    WilayahResolver,
    norm_text,
    parse_int,
)


class NormTextTests(unittest.TestCase):
    def test_ejaan_variasi_menjadi_satu_kunci(self):
        variants = ["Pra Berkembang", "Pra-Berkembang", "Pra- Berkembang", "  PRA   berkembang "]
        self.assertEqual({norm_text(v) for v in variants}, {"pra berkembang"})

    def test_tanda_baca_dan_none(self):
        self.assertEqual(norm_text("D.I. Yogyakarta"), "d i yogyakarta")
        self.assertEqual(norm_text(None), "")
        self.assertEqual(norm_text("---"), "")


class ParseIntTests(unittest.TestCase):
    def test_diterima(self):
        for raw, expected in [("30", 30), ("30.0", 30), ("30,0", 30), (" 7 ", 7), ("0", 0)]:
            self.assertEqual(parse_int(raw), expected, raw)

    def test_ditolak(self):
        for raw in ["abc", "12.5", "1.234", "", "3 guru", "--1"]:
            with self.assertRaises(ValueError, msg=raw):
                parse_int(raw)


CHOICES = [("dinas", "Dinas Pendidikan"), ("mitra", "Mitra")]


class ChoiceResolverTests(unittest.TestCase):
    def test_cocok_label_nilai_dan_ejaan(self):
        r = ChoiceResolver(CHOICES)
        self.assertEqual(r.resolve("Dinas Pendidikan"), "dinas")
        self.assertEqual(r.resolve("dinas"), "dinas")
        self.assertEqual(r.resolve(" MITRA "), "mitra")
        self.assertIsNone(r.resolve("Pemda"))
        self.assertIsNone(r.resolve(None))

    def test_alias_bawaan_pemda_ke_dinas(self):
        r = ChoiceResolver(CHOICES, {"Pemda": "dinas"})
        self.assertEqual(r.resolve("Pemda"), "dinas")
        self.assertEqual(r.resolve("pemda"), "dinas")

    def test_alias_ke_nilai_yang_tidak_ada_diabaikan(self):
        r = ChoiceResolver(CHOICES, {"Swasta": "swasta"})
        self.assertIsNone(r.resolve("Swasta"))

    def test_options_untuk_pesan_error(self):
        self.assertEqual(ChoiceResolver(CHOICES).options, ["Dinas Pendidikan", "Mitra"])


# ---- Wilayah dengan model tiruan ----


class FakeQS(list):
    def select_related(self, *_args):
        return self

    def all(self):
        return self


class Prov:
    def __init__(self, pk, kode, nama):
        self.pk, self.kode, self.nama = pk, kode, nama


class Kab:
    def __init__(self, pk, kode, nama, provinsi):
        self.pk, self.kode, self.nama, self.provinsi_id = pk, kode, nama, provinsi.pk


class Alias:
    def __init__(self, alias, **kw):
        self.alias = alias
        self.__dict__.update(kw)


def _manager(items):
    return types.SimpleNamespace(objects=FakeQS(items))


class WilayahResolverTests(unittest.TestCase):
    def setUp(self):
        dki = Prov(1, "31", "Daerah Khusus Ibukota Jakarta")
        jabar = Prov(2, "32", "Jawa Barat")
        jateng = Prov(3, "33", "Jawa Tengah")
        sulsel = Prov(4, "73", "Sulawesi Selatan")
        jatim = Prov(5, "35", "Jawa Timur")
        self.provs = dict(dki=dki, jabar=jabar, jateng=jateng, sulsel=sulsel, jatim=jatim)

        self.kota_bandung = Kab(1, "32.73", "Kota Bandung", jabar)
        self.kab_bandung = Kab(2, "32.04", "Kabupaten Bandung", jabar)
        self.kab_bogor = Kab(3, "32.01", "Kabupaten Bogor", jabar)
        self.jakpus = Kab(4, "31.71", "Kota Administrasi Jakarta Pusat", dki)
        self.kota_magelang = Kab(5, "33.71", "Kota Magelang", jateng)
        self.kab_magelang = Kab(6, "33.08", "Kabupaten Magelang", jateng)
        self.makassar = Kab(7, "73.71", "Kota Makassar", sulsel)
        self.kab_malang = Kab(8, "35.07", "Kabupaten Malang", jatim)
        self.kota_malang = Kab(9, "35.73", "Kota Malang", jatim)
        # "Kabupaten Blitar" hanya ada di Jawa Timur; dipakai untuk uji mismatch
        self.kab_blitar = Kab(10, "35.05", "Kabupaten Blitar", jatim)
        kabs = [
            self.kota_bandung, self.kab_bandung, self.kab_bogor, self.jakpus,
            self.kota_magelang, self.kab_magelang, self.makassar, self.kab_malang,
            self.kota_malang, self.kab_blitar,
        ]  # fmt: skip

        stub = types.ModuleType("apps.referensi.models")
        stub.Provinsi = _manager(self.provs.values())
        stub.KabKota = _manager(kabs)
        stub.AliasProvinsi = _manager(
            [
                Alias("DKI Jakarta", provinsi=dki),
                Alias("Jakarta", provinsi=dki),
                Alias("Jawa Barat", provinsi=jateng),
            ]
        )
        stub.AliasKabKota = _manager(
            [
                Alias("Kota Makasar", kabkota=self.makassar),  # salah ketik pada file asli
                Alias("Kota Magelan", kabkota=self.kota_magelang),
                Alias("Jakarta Pusat", kabkota=self.jakpus),
            ]
        )
        patcher = mock.patch.dict(sys.modules, {"apps.referensi.models": stub})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.r = WilayahResolver()

    # provinsi
    def test_provinsi_resmi_dan_alias(self):
        self.assertIs(self.r.resolve_provinsi("Jawa Tengah").obj, self.provs["jateng"])
        self.assertIs(self.r.resolve_provinsi("jawa  tengah").obj, self.provs["jateng"])
        self.assertIs(self.r.resolve_provinsi("DKI Jakarta").obj, self.provs["dki"])

    def test_provinsi_alias_yang_berbenturan_ditolak(self):
        res = self.r.resolve_provinsi("Jawa Barat")
        self.assertEqual(res.problem, "ambiguous")

    def test_teks_terulang_tidak_dikoreksi_otomatis(self):
        self.assertEqual(self.r.resolve_provinsi("Jawa Barat Jawa Barat").problem, "unknown")
        self.assertEqual(
            self.r.resolve_kabkota("Kabupaten Malang Kabupaten Malang").problem,
            "unknown",
        )

    def test_provinsi_tidak_dikenal(self):
        res = self.r.resolve_provinsi("Atlantis")
        self.assertEqual(res.problem, "unknown")
        self.assertIn("Atlantis", res.detail)

    # kabupaten/kota
    def test_nama_lengkap_dan_alias_salah_ketik(self):
        self.assertIs(self.r.resolve_kabkota("Kota Bandung").obj, self.kota_bandung)
        self.assertIs(self.r.resolve_kabkota("kota   bandung").obj, self.kota_bandung)
        self.assertIs(self.r.resolve_kabkota("Kota Makasar").obj, self.makassar)
        self.assertIs(self.r.resolve_kabkota("Kota Magelan").obj, self.kota_magelang)
        self.assertIs(self.r.resolve_kabkota("Jakarta Pusat").obj, self.jakpus)

    def test_awalan_administrasi_dinormalisasi_dengan_aman(self):
        self.assertIs(self.r.resolve_kabkota("Kota Adm. Jakarta Pusat").obj, self.jakpus)
        self.assertIs(self.r.resolve_kabkota("Adm. Jakarta Pusat").obj, self.jakpus)

    def test_nama_tanpa_awalan_unik_diterima(self):
        self.assertIs(self.r.resolve_kabkota("Bogor").obj, self.kab_bogor)
        self.assertIs(self.r.resolve_kabkota("Kota Administrasi Jakarta Pusat").obj, self.jakpus)

    def test_nama_tanpa_awalan_ambigu_ditolak_bukan_ditebak(self):
        res = self.r.resolve_kabkota("Bandung")
        self.assertEqual(res.problem, "ambiguous")
        self.assertIsNone(res.obj)
        self.assertIn("Kabupaten Bandung", res.detail)
        self.assertIn("Kota Bandung", res.detail)

    def test_awalan_eksplisit_menghilangkan_ambiguitas(self):
        self.assertIs(self.r.resolve_kabkota("Kabupaten Bandung").obj, self.kab_bandung)
        self.assertIs(self.r.resolve_kabkota("Kab. Bandung").obj, self.kab_bandung)

    def test_provinsi_tidak_menyelesaikan_ambiguitas_dalam_provinsi_yang_sama(self):
        res = self.r.resolve_kabkota("Bandung", self.provs["jabar"])
        self.assertEqual(res.problem, "ambiguous")

    def test_provinsi_menyaring_antar_provinsi(self):
        # "Magelang" ada di Jawa Tengah saja, tapi "Malang" kota/kab keduanya di Jatim
        res = self.r.resolve_kabkota("Kota Malang", self.provs["jatim"])
        self.assertIs(res.obj, self.kota_malang)

    def test_kabkota_di_provinsi_lain_dilaporkan_mismatch(self):
        res = self.r.resolve_kabkota("Kabupaten Blitar", self.provs["jabar"])
        self.assertEqual(res.problem, "mismatch")
        self.assertIn("Jawa Timur", res.detail)
        self.assertIn("Jawa Barat", res.detail)

    def test_kabkota_tidak_dikenal(self):
        self.assertEqual(self.r.resolve_kabkota("Kota Antah Berantah").problem, "unknown")

    def test_provinsi_by_pk_tersedia_untuk_derivasi(self):
        self.assertEqual(self.r.provinsi_by_pk[self.kab_bogor.provinsi_id].nama, "Jawa Barat")


if __name__ == "__main__":
    unittest.main()
