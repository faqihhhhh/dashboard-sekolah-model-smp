"""Transformasi kolom rating baseline menjadi hasil indikator format panjang."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from apps.baseline.models import KamusIndikator, LevelIndikator, RatingIndikator
from apps.imports.engine import DEFAULT_NULL_TOKENS, is_null_or_empty
from apps.imports.normalize import ChoiceResolver

RATING_RESOLVER = ChoiceResolver(RatingIndikator.choices)


@dataclass(frozen=True)
class IndicatorValue:
    indikator: KamusIndikator
    rating: str


@dataclass(frozen=True)
class IndicatorIssue:
    header: str
    message: str


@dataclass
class IndicatorTransform:
    values: list[IndicatorValue] = field(default_factory=list)
    issues: list[IndicatorIssue] = field(default_factory=list)
    mapping_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mapping_errors and not self.issues


def transform_indicator_values(
    record: Mapping[str, Any],
    column_map: Mapping[str, KamusIndikator],
    *,
    null_tokens: tuple[str, ...] = DEFAULT_NULL_TOKENS,
    value_maps: Mapping[str, Mapping[str, str]] | None = None,
) -> IndicatorTransform:
    """Ubah nilai rating yang dipetakan manual menjadi baris panjang.

    Pemetaan header ke indikator sepenuhnya diberikan pemanggil. Sel kosong atau token null
    diabaikan agar pembaruan tidak menghapus rating yang sudah tersimpan.
    """
    result = IndicatorTransform()
    value_maps = value_maps or {}
    seen_indicators: dict[tuple[str, str, str], str] = {}

    for header, indicator in column_map.items():
        indicator_key = (indicator.kerangka, indicator.level, indicator.kode)
        previous_header = seen_indicators.get(indicator_key)
        if previous_header is not None:
            result.mapping_errors.append(
                f"Indikator {indicator.kode} dipetakan dari dua kolom: "
                f"{previous_header} dan {header}."
            )
            continue
        seen_indicators[indicator_key] = header
        if indicator.level != LevelIndikator.L3:
            result.mapping_errors.append(f"Kolom '{header}' harus dipetakan ke indikator Level 3.")
            continue
        if header not in record:
            result.mapping_errors.append(f"Header '{header}' tidak ada pada baris sumber.")
            continue

        raw = record[header]
        if is_null_or_empty(raw, null_tokens):
            continue
        raw_text = str(raw).strip()
        canonical = value_maps.get(header, {}).get(raw_text, raw_text)
        rating = RATING_RESOLVER.resolve(canonical)
        if rating is None:
            result.issues.append(
                IndicatorIssue(
                    header=header,
                    message=f"Rating '{raw_text}' pada kolom '{header}' tidak dikenali.",
                )
            )
            continue
        result.values.append(IndicatorValue(indikator=indicator, rating=rating))

    return result
