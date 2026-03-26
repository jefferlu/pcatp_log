"""
Parser for TestCriteria_*.config files.

Preserves every original line (comments, sections, blank lines, inline
comments) and allows targeted modification of _Max / _Min values so the
exported content is diff-minimal against the original.
"""
from __future__ import annotations

import re


class CriteriaConfig:
    """Mutable in-memory representation of a TestCriteria config file."""

    def __init__(self, lines: list[str]) -> None:
        self._lines: list[str] = lines
        # key → line index (last occurrence wins for duplicate keys)
        self._line_idx: dict[str, int]   = {}
        # key → current float value
        self._values:   dict[str, float] = {}
        self._parse()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes) -> "CriteriaConfig":
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        return cls(text.splitlines(keepends=True))

    # ------------------------------------------------------------------
    # Internal parser
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        for i, line in enumerate(self._lines):
            kv = self._extract_kv(line)
            if kv is None:
                continue
            key, val_str = kv
            if key.endswith("_Max") or key.endswith("_Min"):
                try:
                    self._line_idx[key] = i
                    self._values[key]   = float(val_str)
                except ValueError:
                    pass

    @staticmethod
    def _extract_kv(line: str) -> tuple[str, str] | None:
        """Return (key, numeric_value_str) for a valid key=value line, else None."""
        content = line.strip()
        if not content or content.startswith(";") or content.startswith("["):
            return None
        if "=" not in content:
            return None
        key_part, rest = content.split("=", 1)
        key = key_part.strip()
        if not key:
            return None
        # Strip inline comment, then take first token as the numeric value
        val_str = rest.split(";")[0].strip()
        # Must be a plain number (int or float, no letters)
        if not re.match(r"^[\d.]+$", val_str):
            return None
        return key, val_str

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def params(self) -> dict[str, float]:
        """All _Max / _Min keys and their current values."""
        return dict(self._values)

    def get(self, key: str) -> float | None:
        return self._values.get(key)

    def set(self, key: str, new_value: float) -> bool:
        """Update a _Max / _Min key in-place.  Returns False if key not found."""
        if key not in self._line_idx:
            return False
        idx      = self._line_idx[key]
        old_line = self._lines[idx]

        # Determine original numeric string to decide formatting
        kv = self._extract_kv(old_line)
        if kv is None:
            return False
        _, old_val_str = kv

        if "." in old_val_str:
            # Preserve same number of decimal places as original
            decimals  = len(old_val_str.split(".")[1])
            new_str   = f"{new_value:.{decimals}f}"
        else:
            new_str = str(int(round(new_value)))

        # Replace the numeric value after '=' (first occurrence only)
        self._lines[idx] = re.sub(
            r"(=\s*)[\d.]+",
            lambda m: m.group(1) + new_str,
            old_line,
            count=1,
        )
        self._values[key] = new_value
        return True

    def export(self) -> str:
        """Return the full config content with all modifications applied."""
        return "".join(self._lines)

    # ------------------------------------------------------------------
    # Convenience: base-name helpers
    # ------------------------------------------------------------------

    def base_names(self) -> set[str]:
        """Return the set of all base names (key without _Max / _Min suffix)."""
        result = set()
        for key in self._values:
            result.add(key[:-4])  # both '_Max' and '_Min' are 4 chars
        return result

    def get_pair(self, base: str) -> tuple[float | None, float | None]:
        """Return (min_value, max_value) for a given base name."""
        return self._values.get(f"{base}_Min"), self._values.get(f"{base}_Max")
