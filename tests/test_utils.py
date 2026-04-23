"""Unit tests for utils.normalize_city and utils.display_city.

Run with: pytest tests/test_utils.py -v
"""
import sys
from pathlib import Path

# Allow running pytest from project root or tests/ dir
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from utils import normalize_city, display_city, CITY_ALIASES, CITY_DISPLAY_MAP


class TestNormalizeCity:
    """normalize_city() maps user input / legacy variants to canonical form."""

    def test_zhongqu_variants_all_map_to_canonical(self):
        assert normalize_city("中區") == "中區聯盟"
        assert normalize_city("中區縣") == "中區聯盟"
        assert normalize_city("中區縣市") == "中區聯盟"

    def test_zhongqu_canonical_passes_through(self):
        assert normalize_city("中區聯盟") == "中區聯盟"

    def test_simplified_traditional_taiwan(self):
        assert normalize_city("台北") == "臺北市"
        assert normalize_city("台北市") == "臺北市"
        assert normalize_city("台南") == "臺南市"
        assert normalize_city("台南市") == "臺南市"

    def test_missing_suffix_shortforms(self):
        assert normalize_city("桃園") == "桃園市"
        assert normalize_city("高雄") == "高雄市"
        assert normalize_city("新北") == "新北市"
        assert normalize_city("新竹") == "新竹市"
        assert normalize_city("屏東") == "屏東縣"
        assert normalize_city("澎湖") == "澎湖縣"
        assert normalize_city("金門") == "金門縣"
        assert normalize_city("連江") == "連江縣"

    def test_colloquial_name(self):
        assert normalize_city("馬祖") == "連江縣"

    def test_canonical_cities_passthrough(self):
        canonical = [
            "中區聯盟", "屏東縣", "新北市", "新竹市", "桃園市",
            "澎湖縣", "臺北市", "臺南市", "連江縣", "金門縣", "高雄市",
        ]
        for city in canonical:
            assert normalize_city(city) == city, f"{city} should pass through unchanged"

    def test_unknown_city_passthrough(self):
        assert normalize_city("花蓮縣") == "花蓮縣"
        assert normalize_city("某個不存在的縣") == "某個不存在的縣"

    def test_none_input(self):
        assert normalize_city(None) is None

    def test_empty_string(self):
        assert normalize_city("") == ""

    def test_idempotent(self):
        """Applying normalize twice should equal applying once."""
        for city in ["中區", "台北", "桃園", "臺北市", "中區聯盟", "高雄", None, ""]:
            once = normalize_city(city)
            twice = normalize_city(once)
            assert once == twice, f"Not idempotent for {city!r}"


class TestDisplayCity:
    """display_city() maps canonical form to user-friendly display form."""

    def test_zhongqu_displays_as_short_form(self):
        assert display_city("中區聯盟") == "中區"

    def test_other_canonical_cities_passthrough(self):
        # Display layer only transforms 中區聯盟 — other cities keep their names
        for city in ["臺北市", "臺南市", "桃園市", "新北市", "高雄市", "連江縣", "金門縣"]:
            assert display_city(city) == city

    def test_none_input(self):
        assert display_city(None) is None

    def test_empty_string(self):
        assert display_city("") == ""

    def test_unknown_city_passthrough(self):
        assert display_city("花蓮縣") == "花蓮縣"


class TestRoundTrip:
    """Round-trip and interaction between normalize_city and display_city."""

    def test_normalize_then_display_recovers_shortform(self):
        """User types '中區' → normalize to canonical → display as '中區'."""
        assert display_city(normalize_city("中區")) == "中區"
        assert display_city(normalize_city("中區縣市")) == "中區"
        assert display_city(normalize_city("中區聯盟")) == "中區"

    def test_display_then_normalize_recovers_canonical(self):
        """Stored canonical → display → user re-submits display form → normalize back."""
        assert normalize_city(display_city("中區聯盟")) == "中區聯盟"
        assert normalize_city(display_city("臺北市")) == "臺北市"

    def test_filter_scenario(self):
        """Realistic filter scenario: user types shortform, stored data is canonical."""
        user_input = "台北"
        stored_city = "臺北市"
        assert normalize_city(user_input) == normalize_city(stored_city)


class TestAliasMapIntegrity:
    """Sanity checks on the alias map itself."""

    def test_all_alias_targets_are_canonical(self):
        """Every alias target should be a real GT city (passthrough under normalize)."""
        for alias, target in CITY_ALIASES.items():
            assert normalize_city(target) == target, (
                f"Alias target {target!r} (from {alias!r}) is not canonical"
            )

    def test_no_alias_cycles(self):
        """Applying normalize twice on any alias key should converge."""
        for alias in CITY_ALIASES:
            once = normalize_city(alias)
            twice = normalize_city(once)
            assert once == twice

    def test_display_map_covers_only_canonical(self):
        """Display map keys should all be canonical (normalize passthrough)."""
        for key in CITY_DISPLAY_MAP:
            assert normalize_city(key) == key, (
                f"Display map key {key!r} is not canonical"
            )
