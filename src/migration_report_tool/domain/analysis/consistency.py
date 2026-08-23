"""Consistency analysis helpers for the DATA Analysis columns.

The Analysis block uses one rule for NAME / FEEDER / SMART / TYPE:

* blank source values are ignored;
* one non-blank value is considered consistent (TRUE);
* two or more non-blank values are TRUE only when their normalized values agree;
* if every source is blank, the result is blank (unknown / not applicable), not TRUE.

Each business field has its own normalizer so representation differences do not
create false mismatches (for example ABN2-03 vs JED-NTH-ABN2-3).
"""
from __future__ import annotations

import re
import ipaddress
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from ...parsers import clean, normalize_key

Normalizer = Callable[[object], str]


@dataclass(frozen=True)
class ConsistencyResult:
    """Normalized consistency result plus raw/normalized values used for the decision."""

    value: bool | None
    normalized_by_source: dict[str, str]
    raw_by_source: dict[str, str]

    @property
    def display(self) -> str:
        if self.value is None:
            return ""
        return "TRUE" if self.value else "FALSE"

    @property
    def distinct_values(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.normalized_by_source.values())))


def normalize_name(value: object) -> str:
    """Normalize RMU/cabinet names while preserving alphanumeric identifiers."""
    text = normalize_key(value).strip().upper()
    return "" if text in {"", "0", "NULL", "NONE", "N/A", "NA", "-"} else text


def _tokens(value: object) -> list[str]:
    return re.findall(r"[A-Z0-9]+", clean(value).upper())


def _normalize_numeric_token(token: str) -> str:
    if token.isdigit():
        # Feeder 03 and feeder 3 are the same logical feeder.
        return str(int(token))
    return token


# FEEDER comparison uses the complete logical feeder identity:
#
#     station/site token + feeder number
#
# Region prefixes such as JED-NTH are presentation/routing prefixes and are
# ignored, but the station token itself is business-significant.  Therefore
# ABH-22 and JED-NTH-ABH-22 are the same feeder, while ABN-22 is a different
# feeder even though the numeric suffix is also 22.  The current ADMS
# convention encodes feeder N as AH3NN:
#
#   ABN-AH312            -> ABN-12
#   ABN-AH301            -> ABN-1
#   JED-NTH-ABH-AH303    -> ABH-3
#
# Normal source values use a trailing numeric token:
#
#   ABH-03               -> ABH-3
#   JED-NTH-ABH-3        -> ABH-3
#   JED-NTH-ABN-3        -> ABN-3   (different feeder)
#
# This is a confirmed project rule.  If a feeder number is present without an
# explicit station token, the selected repository site is used as the station
# hint.  Unknown textual encodings remain conservative so they cannot silently
# compare equal.
_ADMS_AH3_SUFFIX = re.compile(r"^AH3(?P<feeder>\d{1,2})$", re.I)


def _logical_feeder_number(tokens: list[str]) -> str:
    if not tokens:
        return ""
    last = tokens[-1]
    match = _ADMS_AH3_SUFFIX.fullmatch(last)
    if match:
        return str(int(match.group("feeder")))
    if last.isdigit():
        return str(int(last))
    return ""


def _site_token_hint(site_name: str | None) -> str:
    """Return the station token implied by the selected repository site.

    Repository folders commonly use labels such as ``1-ABH`` / ``1-ABN2``
    while older configuration may contain labels such as ``JEDDAH_ABH`` or
    ``ABH110``.  Only this fallback path uses the repository label; an explicit
    station token carried by a feeder value always wins.
    """
    tokens = _tokens(site_name or "")
    candidates = [token for token in tokens if not token.isdigit()]
    if not candidates:
        return ""
    token = candidates[-1]
    # Common voltage suffixes may be appended to the station code in a site
    # label (for example ABH110).  Do not strip single digits because ABN2 is a
    # valid station token.
    match = re.fullmatch(r"(?P<site>[A-Z][A-Z0-9]*?)(?:110|132|33)$", token)
    return match.group("site") if match else token


def _explicit_feeder_site_token(tokens: list[str]) -> str:
    """Return the station token immediately preceding a decoded feeder suffix."""
    if len(tokens) < 2:
        return ""
    candidate = tokens[-2]
    # Generic labels do not prove station identity; use the selected-site hint
    # instead when these are encountered.
    if candidate in {"FEEDER", "FDR", "FD", "NO", "NUMBER"}:
        return ""
    return candidate


def normalize_feeder_for_compare(value: object, site_name: str | None = None) -> str:
    """Return ``<station>-<feeder>`` for FEEDER consistency analysis.

    The station component is mandatory whenever it can be determined.  This
    prevents same-number feeders from different stations from comparing equal.

    Examples::

        ABN-12                    -> ABN-12
        JED-NTH-ABN-12            -> ABN-12
        ABN-AH312                 -> ABN-12
        ABN-01                    -> ABN-1
        JED-NTH-ABH-AH303         -> ABH-3
        JED-NTH-ABN-AH303         -> ABN-3

    ``ABH-3`` and ``ABN-3`` are therefore different logical feeders.
    """
    raw = clean(value).upper()
    if raw in {"", "0", "NULL", "NONE", "N/A", "NA", "-"}:
        return ""
    tokens = _tokens(raw)
    if not tokens:
        return ""

    logical_number = _logical_feeder_number(tokens)
    if logical_number:
        station = _explicit_feeder_site_token(tokens) or _site_token_hint(site_name)
        return f"{station}-{logical_number}" if station else logical_number

    # No confirmed numeric feeder suffix was found.  Keep a conservative
    # textual representation.  If the selected site token sequence is present,
    # discard only prefixes before it (e.g. JED-NTH); otherwise retain all
    # tokens so an unknown encoding cannot accidentally compare equal.
    selected_site_tokens = _tokens(site_name or "")
    if selected_site_tokens:
        # Repository folders may contain a sequence prefix such as ``1-ABN``.
        # Try every suffix of the configured site label, longest first, and use
        # the first exact sequence found in the source value.
        candidates = [selected_site_tokens[i:] for i in range(len(selected_site_tokens))]
        candidates.sort(key=len, reverse=True)
        for candidate in candidates:
            if not candidate:
                continue
            n = len(candidate)
            for i in range(0, len(tokens) - n + 1):
                if tokens[i:i+n] == candidate:
                    tokens = tokens[i:]
                    return "-".join(_normalize_numeric_token(token) for token in tokens)

        # ``1-ABH`` should also match an embedded ``ABH`` even though the
        # repository sequence number is not carried in source feeder names.
        site_hint = _site_token_hint(site_name)
        if site_hint:
            for i, token in enumerate(tokens):
                if token == site_hint:
                    return "-".join(_normalize_numeric_token(token) for token in tokens[i:])

    return "-".join(_normalize_numeric_token(token) for token in tokens)

def normalize_ip(value: object) -> str:
    """Normalize IPv4/IPv6 addresses for Driver-info vs ADMS-channel checks.

    CIDR suffixes are accepted (``172.20.1.10/24`` -> ``172.20.1.10``).
    An unknown non-empty token is retained so contradictory source values remain
    visible instead of being silently ignored.
    """
    text = clean(value).strip()
    if text.upper() in {"", "0", "NULL", "NONE", "N/A", "NA", "-"}:
        return ""
    try:
        if "/" in text:
            return str(ipaddress.ip_interface(text).ip)
        return str(ipaddress.ip_address(text))
    except ValueError:
        return text.casefold()


def normalize_smart(value: object) -> str:
    """Normalize the different SMART/NORMAL conventions used by source files."""
    text = clean(value).upper()
    if not text:
        return ""

    compact = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    words = set(re.findall(r"[A-Z0-9]+", text))

    smart_aliases = {"SMART", "SMR", "YES", "TRUE", "Y", "1"}
    normal_aliases = {"NORMAL", "NONSMART", "NON_SMART", "NO", "FALSE", "N", "0"}

    # SE examples: "SMART HT", "SMART NOP HT", "NORMAL NOP".
    if words & {"SMART", "SMR"}:
        return "SMART"
    if "NORMAL" in words or compact.startswith("NON_SMART") or compact.startswith("NONSMART"):
        return "NORMAL"
    if compact in smart_aliases:
        return "SMART"
    if compact in normal_aliases:
        return "NORMAL"

    # Keep an unknown explicit value so two contradictory source conventions do
    # not become invisible. Blank is the only value that is ignored.
    return compact


def normalize_type(value: object) -> str:
    """Normalize RMU cabinet type, e.g. 2L1T / 3L1T."""
    text = clean(value).upper()
    if text in {"", "0", "NULL", "NONE", "N/A", "NA", "-"}:
        return ""
    match = re.search(r"(?<![A-Z0-9])(\d+L(?:\d+T)?)(?![A-Z0-9])", text)
    return match.group(1) if match else re.sub(r"\s+", "", text)


def compare_consistency(
    values_by_source: Mapping[str, object] | Iterable[tuple[str, object]],
    normalizer: Normalizer,
) -> ConsistencyResult:
    """Apply the common blank-ignoring consistency rule."""
    items = values_by_source.items() if isinstance(values_by_source, Mapping) else values_by_source
    normalized: dict[str, str] = {}
    raw_values: dict[str, str] = {}
    for source, raw in items:
        value = normalizer(raw)
        if value:
            key = str(source)
            normalized[key] = value
            raw_values[key] = clean(raw)

    if not normalized:
        return ConsistencyResult(None, normalized, raw_values)
    return ConsistencyResult(len(set(normalized.values())) == 1, normalized, raw_values)


def first_value(row: Mapping[str, object], *keys: str) -> object:
    """Return the first non-blank value from a row using source-specific aliases."""
    for key in keys:
        value = row.get(key)
        if clean(value):
            return value
    return ""
