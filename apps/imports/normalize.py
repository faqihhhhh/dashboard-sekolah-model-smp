"""Normalisasi nilai sel: teks, angka, pilihan tetap (choices), dan nama wilayah.

Bagian atas file (norm_text, parse_int, ChoiceResolver) tidak butuh Django dan bisa diuji
tersendiri. WilayahResolver memakai model referensi, jadi Django diimpor di dalamnya.

Prinsip: pencocokan bersifat toleran terhadap ejaan ("Pra Berkembang", "Pra-Berkembang",
"Pra- Berkembang" dianggap sama) tetapi TIDAK menebak. Bila tidak ada kecocokan yang pasti,
hasilnya "tidak dikenali" atau "ambigu" dan admin yang memutuskan lewat pemetaan nilai.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_INT = re.compile(r"^[+-]?\d+(?:[.,]0+)?$")


def norm_text(text: str | None) -> str:
    """Kunci pencocokan: huruf kecil, tanda baca menjadi spasi, spasi dirapikan.

    "Pra- Berkembang" -> "pra berkembang"; "D.I. Yogyakarta" -> "d i yogyakarta".
    """
    if text is None:
        return ""
    return _NON_ALNUM.sub(" ", str(text).lower()).strip()


def parse_int(raw: str) -> int:
    """Teks menjadi bilangan bulat. "30", "30.0", "30,0" diterima; selain itu ValueError."""
    text = str(raw).strip().replace(" ", "")
    if not _INT.match(text):
        raise ValueError(raw)
    return int(re.split(r"[.,]", text)[0])


class ChoiceResolver:
    """Mencocokkan teks bebas ke nilai tersimpan sebuah field ber-choices.

    Urutan: alias eksplisit (pemetaan admin / bawaan dataset), lalu nilai tersimpan, lalu label.
    Semuanya dinormalisasi lebih dulu. Alias yang menunjuk nilai yang tidak ada diabaikan.
    """

    def __init__(self, flatchoices: Iterable[tuple], aliases: Mapping[str, str] | None = None):
        self._labels: list[str] = []
        self._index: dict[str, str] = {}
        valid = set()
        for value, label in flatchoices:
            valid.add(str(value))
            self._labels.append(str(label))
            self._index.setdefault(norm_text(str(label)), str(value))
        for value in valid:
            self._index.setdefault(norm_text(value), value)
        # alias menang atas label/nilai bila bentrok
        for text, value in (aliases or {}).items():
            if str(value) in valid and norm_text(text):
                self._index[norm_text(text)] = str(value)

    @property
    def options(self) -> list[str]:
        return list(self._labels)

    def resolve(self, raw: str | None) -> str | None:
        return self._index.get(norm_text(raw))


# ---------------------------------------------------------------------------
# Wilayah
# ---------------------------------------------------------------------------

_KAB_PREFIXES = ("kabupaten administrasi", "kota administrasi", "kabupaten", "kab", "kota")


def _bare_name(norm: str) -> str:
    """Nama tanpa awalan jenis: "kota bandung" -> "bandung"."""
    for prefix in _KAB_PREFIXES:
        if norm.startswith(prefix + " "):
            return norm[len(prefix) + 1 :]
    return norm


def _expand_abbreviation(norm: str) -> str:
    """Meluaskan awalan wilayah yang diizinkan tanpa mengubah nama sisanya."""
    for short, full in (
        ("kab adm ", "kabupaten administrasi "),
        ("kota adm ", "kota administrasi "),
        ("kab ", "kabupaten "),
    ):
        if norm.startswith(short):
            return full + norm[len(short) :]
    if norm.startswith("adm "):
        return norm[4:]
    return norm


@dataclass
class Resolved:
    obj: object | None = None
    problem: str | None = None  # None | "unknown" | "ambiguous" | "mismatch"
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.problem is None


@dataclass
class WilayahResolver:
    """Mencocokkan nama provinsi dan kabupaten/kota ke data referensi.

    Index dibangun sekali per impor (38 provinsi + ~514 kab/kota + alias; ringan).
    """

    provinsi_by_pk: dict = field(default_factory=dict, init=False)
    _prov_index: dict = field(default_factory=dict, init=False)
    _kab_full: dict = field(default_factory=dict, init=False)
    _kab_bare: dict = field(default_factory=dict, init=False)
    _kab_alias_keys: set[str] = field(default_factory=set, init=False)

    def __post_init__(self):
        from apps.referensi.models import AliasKabKota, AliasProvinsi, KabKota, Provinsi

        for provinsi in Provinsi.objects.all():
            self.provinsi_by_pk[provinsi.pk] = provinsi
            self._add(self._prov_index, norm_text(provinsi.nama), provinsi)
        for alias in AliasProvinsi.objects.select_related("provinsi"):
            self._add(self._prov_index, norm_text(alias.alias), alias.provinsi)

        kabkota = list(KabKota.objects.all())
        for kab in kabkota:
            self._add(self._kab_full, norm_text(kab.nama), kab)
            self._add(self._kab_bare, _bare_name(norm_text(kab.nama)), kab)
        for alias in AliasKabKota.objects.select_related("kabkota"):
            alias_key = norm_text(alias.alias)
            self._kab_alias_keys.add(alias_key)
            self._add(self._kab_full, alias_key, alias.kabkota)

    def has_kabkota_alias(self, raw: str) -> bool:
        """True bila ejaan wilayah pernah disetujui sebagai alias kabupaten/kota."""
        return norm_text(raw) in self._kab_alias_keys

    @staticmethod
    def _add(index: dict, key: str, kab) -> None:
        bucket = index.setdefault(key, [])
        if kab not in bucket:
            bucket.append(kab)

    # -- provinsi --

    def resolve_provinsi(self, raw: str) -> Resolved:
        key = norm_text(raw)
        candidates = self._prov_index.get(key, [])
        if not candidates:
            return Resolved(problem="unknown", detail=f"provinsi '{raw}' tidak dikenali")
        if len(candidates) > 1:
            names = ", ".join(sorted({prov.nama for prov in candidates}))
            return Resolved(
                problem="ambiguous",
                detail=f"'{raw}' ambigu ({names}); periksa alias wilayah yang terdaftar",
            )
        return Resolved(obj=candidates[0])

    # -- kabupaten/kota --

    def resolve_kabkota(self, raw: str, provinsi=None) -> Resolved:
        """Cocokkan nama (opsional dibatasi provinsi).

        Nama lengkap/alias didahulukan; nama tanpa awalan ("Bandung") hanya dipakai bila tidak
        ada yang cocok penuh. Lebih dari satu kandidat dalam cakupan yang sama = ambigu.
        """
        key = _expand_abbreviation(norm_text(raw))
        candidates = self._kab_full.get(key) or self._kab_bare.get(_bare_name(key)) or []
        if not candidates:
            return Resolved(problem="unknown", detail=f"kabupaten/kota '{raw}' tidak dikenali")

        if provinsi is not None:
            inside = [k for k in candidates if k.provinsi_id == provinsi.pk]
            if not inside:
                names = {self.provinsi_by_pk[k.provinsi_id].nama for k in candidates}
                return Resolved(
                    problem="mismatch",
                    detail=f"'{raw}' ada di {', '.join(sorted(names))}, bukan di {provinsi.nama}",
                )
            candidates = inside

        if len(candidates) > 1:
            names = ", ".join(sorted(k.nama for k in candidates))
            return Resolved(
                problem="ambiguous",
                detail=f"'{raw}' ambigu ({names}); tulis lengkap atau petakan manual",
            )
        return Resolved(obj=candidates[0])
