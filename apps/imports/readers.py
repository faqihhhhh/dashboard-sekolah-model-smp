"""Membaca file .xlsx dan .csv menjadi tabel teks yang aman dan seragam.

Prinsip: pembaca TIDAK menebak apa pun. Sheet, baris header, encoding, dan pemisah CSV
dipilih admin; pembaca hanya membaca dan membersihkan sel menjadi teks.
"""

import csv
import datetime as dt
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # batas isi .xlsx setelah dibuka (anti zip bomb)
MAX_ROWS = 50_000
MAX_COLS = 300

ENCODINGS = {"utf-8": "utf-8-sig", "windows-1252": "cp1252"}  # nama pilihan -> codec Python
DELIMITERS = {",", ";", "\t"}
HEADER_JOIN = " | "


class ReaderError(ValueError):
    """Masalah pada file yang pesannya aman ditampilkan kepada admin."""


@dataclass
class Table:
    name: str
    rows: list[list[str | None]]  # SEMUA baris (termasuk header); sel sudah berupa teks/None
    n_cols: int


@dataclass(frozen=True)
class Column:
    index: int  # 0-based
    letter: str  # A, B, ... AA
    header: str  # header gabungan (lihat build_columns)


# ---------- pembersihan sel ----------


def cell_to_text(value) -> str | None:
    """Mengubah nilai sel (angka, tanggal, teks) menjadi teks bersih; kosong -> None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, dt.datetime):
        return value.date().isoformat() if value.time() == dt.time(0) else value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    text = " ".join(str(value).replace(" ", " ").split())  # NBSP -> spasi, rapikan spasi
    return text or None


# ---------- pemeriksaan file ----------


def _check_extension(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".xls":
        raise ReaderError("Format .xls lama tidak didukung. Simpan ulang file sebagai .xlsx.")
    if suffix == ".xlsm":
        raise ReaderError("File dengan makro (.xlsm) ditolak. Simpan ulang sebagai .xlsx.")
    if suffix not in {".xlsx", ".csv"}:
        raise ReaderError("Hanya file .xlsx dan .csv yang dapat diimpor.")
    return suffix


def _check_xlsx_safety(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise ReaderError("Berkas ini bukan file Excel (.xlsx) yang valid.")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names:
            raise ReaderError("Berkas ini bukan file Excel (.xlsx) yang valid.")
        if any(name.lower().endswith("vbaproject.bin") for name in names):
            raise ReaderError("File berisi makro dan ditolak. Simpan ulang sebagai .xlsx biasa.")
        if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
            raise ReaderError("Isi file terlalu besar setelah dibuka.")


def _check_size(path: Path) -> None:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ReaderError(f"File melebihi batas {MAX_FILE_BYTES // (1024 * 1024)} MB.")


def _to_table(name: str, raw_rows: Iterator[Sequence]) -> Table:
    rows: list[list[str | None]] = []
    for count, raw in enumerate(raw_rows, start=1):
        if count > MAX_ROWS:
            raise ReaderError(f"File melebihi batas {MAX_ROWS:,} baris.".replace(",", "."))
        if len(raw) > MAX_COLS:
            raise ReaderError(f"File melebihi batas {MAX_COLS} kolom.")
        rows.append([cell_to_text(v) for v in raw])
    while rows and all(v is None for v in rows[-1]):  # buang baris kosong di ujung
        rows.pop()
    n_cols = max((len(r) for r in rows), default=0)
    for row in rows:
        row.extend([None] * (n_cols - len(row)))
    return Table(name=name, rows=rows, n_cols=n_cols)


# ---------- API publik ----------


def list_sheets(path: str | Path) -> list[str]:
    path = Path(path)
    suffix = _check_extension(path)
    _check_size(path)
    if suffix == ".csv":
        return ["CSV"]
    _check_xlsx_safety(path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def load_table(
    path: str | Path, *, sheet: str | None = None, encoding: str = "utf-8", delimiter: str = ";"
) -> Table:
    """Membaca satu sheet (xlsx) atau seluruh file (csv).

    encoding dan delimiter hanya berlaku untuk CSV dan WAJIB dipilih eksplisit oleh pemanggil.
    """
    path = Path(path)
    suffix = _check_extension(path)
    _check_size(path)
    if suffix == ".csv":
        return _load_csv(path, encoding, delimiter)
    return _load_xlsx(path, sheet)


def _load_xlsx(path: Path, sheet: str | None) -> Table:
    _check_xlsx_safety(path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        name = sheet or workbook.sheetnames[0]
        if name not in workbook.sheetnames:
            available = ", ".join(workbook.sheetnames)
            raise ReaderError(f"Sheet '{name}' tidak ada. Tersedia: {available}")
        return _to_table(name, workbook[name].iter_rows(values_only=True))
    finally:
        workbook.close()


def _load_csv(path: Path, encoding: str, delimiter: str) -> Table:
    if encoding not in ENCODINGS:
        raise ReaderError(f"Encoding tidak dikenal. Pilihan: {', '.join(ENCODINGS)}")
    if delimiter not in DELIMITERS:
        raise ReaderError("Pemisah CSV harus koma, titik koma, atau tab.")
    try:
        with path.open(newline="", encoding=ENCODINGS[encoding]) as handle:
            return _to_table("CSV", csv.reader(handle, delimiter=delimiter))
    except UnicodeDecodeError as error:
        raise ReaderError(
            f"File tidak dapat dibaca sebagai {encoding}. Coba pilih encoding lain."
        ) from error
    except csv.Error as error:
        raise ReaderError(f"File CSV tidak dapat dibaca: {error}") from error


# ---------- header dan data ----------


def build_columns(
    table: Table, header_rows: Sequence[int], fill_right: Sequence[int] = ()
) -> list[Column]:
    """Menyusun header tiap kolom dari satu atau beberapa baris header (nomor baris 1-based).

    - Header bertingkat digabung dengan " | ", mis. "PM Level 3 | 1.1.1".
    - Baris yang disebut di fill_right "diisi ke kanan": sel kosong mengikuti sel terisi di
      kirinya (untuk sel gabungan, yang hanya menyimpan nilai di sel paling kiri).
    - Header kembar diberi akhiran (2), (3), ...; kolom tanpa header diberi nama "Kolom X".
    """
    for number in header_rows:
        if not 1 <= number <= len(table.rows):
            raise ReaderError(f"Baris header {number} berada di luar isi file.")
    prepared: dict[int, list[str | None]] = {}
    for number in header_rows:
        row = list(table.rows[number - 1])
        if number in fill_right:
            carry = None
            for i, value in enumerate(row):
                carry = value if value is not None else carry
                row[i] = carry
        prepared[number] = row

    columns: list[Column] = []
    seen: dict[str, int] = {}
    for index in range(table.n_cols):
        letter = get_column_letter(index + 1)
        parts: list[str] = []
        for number in header_rows:
            value = prepared[number][index]
            if value is not None and (not parts or parts[-1] != value):
                parts.append(value)
        header = HEADER_JOIN.join(parts) or f"Kolom {letter}"
        seen[header] = seen.get(header, 0) + 1
        if seen[header] > 1:
            header = f"{header} ({seen[header]})"
        columns.append(Column(index=index, letter=letter, header=header))
    return columns


def iter_records(
    table: Table, columns: Sequence[Column], first_data_row: int
) -> Iterator[tuple[int, dict[str, str | None]]]:
    """Menghasilkan (nomor_baris, {header: teks}) untuk setiap baris data yang tidak kosong."""
    for number in range(first_data_row, len(table.rows) + 1):
        row = table.rows[number - 1]
        if all(value is None for value in row):
            continue
        yield number, {col.header: row[col.index] for col in columns}
