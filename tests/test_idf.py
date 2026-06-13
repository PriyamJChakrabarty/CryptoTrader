"""spec 019 - IDF unit tests (SC-W4).

tests/test_idf.py - >= 6 test cases PASS
"""

from __future__ import annotations

import math

import pytest


class TestComputeIdf:
    def test_single_skill_corpus_all_keywords_present(self):
        """(a) single skill corpus -> idf table contains all keywords."""
        from cryptotrader.learning.evolution.idf import compute_idf

        corpus = [["rsi", "macd", "sma"]]
        result = compute_idf(corpus)
        assert "rsi" in result
        assert "macd" in result
        assert "sma" in result
        # log(1/1) = 0 for single doc
        assert result["rsi"] == pytest.approx(0.0)

    def test_five_skill_corpus_shared_keyword_has_low_idf(self):
        """(b) 5 skill corpus -> shared keyword has low IDF (log(5/k))."""
        from cryptotrader.learning.evolution.idf import compute_idf

        corpus = [
            ["funding", "rsi"],
            ["funding", "macd"],
            ["funding", "news"],
            ["funding", "whale"],
            ["funding", "fed"],
        ]
        result = compute_idf(corpus)
        # "funding" appears in all 5 skills -> IDF = log(5/5) = 0
        assert result["funding"] == pytest.approx(math.log(5 / 5))
        # "rsi" appears in only 1 skill -> IDF = log(5/1) = log(5)
        assert result["rsi"] == pytest.approx(math.log(5 / 1))

    def test_empty_corpus_returns_empty_dict(self):
        """(c) empty corpus -> empty dict."""
        from cryptotrader.learning.evolution.idf import compute_idf

        result = compute_idf([])
        assert result == {}

    def test_keywords_lowercased_in_idf_table(self):
        """Keywords in the IDF table should be lowercased."""
        from cryptotrader.learning.evolution.idf import compute_idf

        corpus = [["RSI", "MACD"], ["Rsi", "whale"]]
        result = compute_idf(corpus)
        # "RSI" and "Rsi" should both merge into "rsi" (appears in 2 docs)
        assert "rsi" in result
        assert "RSI" not in result
        assert result["rsi"] == pytest.approx(math.log(2 / 2))  # = 0

    def test_duplicate_keywords_within_skill_not_double_counted(self):
        """A keyword repeated within a single skill should only count df once."""
        from cryptotrader.learning.evolution.idf import compute_idf

        # "rsi" appears 3 times within skill 0, but df should only count 1
        corpus = [["rsi", "rsi", "rsi"], ["rsi"]]
        result = compute_idf(corpus)
        # "rsi" appears in 2 docs -> IDF = log(2/2) = 0
        assert result["rsi"] == pytest.approx(0.0)


class TestExtractQueryKeywords:
    def test_extracts_field_names_from_snapshot(self):
        """(d) extract field names from a snapshot dict."""
        from cryptotrader.learning.evolution.idf import extract_query_keywords

        snapshot = {"funding_rate": 0.0003, "rsi_14": 65.0, "pair": "BTC/USDT"}
        result = extract_query_keywords(snapshot)
        assert "funding_rate" in result
        assert "rsi_14" in result
        assert "pair" in result

    def test_extracts_string_values(self):
        """String values should also be extracted (lowercased)."""
        from cryptotrader.learning.evolution.idf import extract_query_keywords

        snapshot = {"regime": "HIGH_FUNDING", "pair": "BTC/USDT"}
        result = extract_query_keywords(snapshot)
        assert "high_funding" in result
        assert "btc/usdt" in result

    def test_nested_dict_fields_extracted(self):
        """Field names from nested dicts should also be extracted."""
        from cryptotrader.learning.evolution.idf import extract_query_keywords

        snapshot = {"market": {"open_interest": 1000, "funding_rate": 0.0003}}
        result = extract_query_keywords(snapshot)
        assert "market" in result
        assert "open_interest" in result
        assert "funding_rate" in result

    def test_empty_snapshot_returns_empty_set(self):
        """An empty snapshot returns an empty set."""
        from cryptotrader.learning.evolution.idf import extract_query_keywords

        result = extract_query_keywords({})
        assert result == set()


class TestScoreSkill:
    def test_score_sums_idf_for_matching_keywords(self):
        """(e) score_skill sums IDF (including case-insensitive matches)."""
        from cryptotrader.learning.evolution.idf import score_skill

        idf_table = {"rsi": 1.6, "macd": 1.2, "funding": 0.0}
        query_keywords = {"rsi", "funding", "btc"}
        skill_keywords = ["RSI", "macd", "funding"]  # "RSI" uppercase, should still match
        score = score_skill(skill_keywords, query_keywords, idf_table)
        # "RSI".lower()="rsi" in query -> +1.6
        # "macd" not in query -> +0
        # "funding" in query -> +0.0
        assert score == pytest.approx(1.6)

    def test_empty_intersection_returns_zero(self):
        """(f) score_skill with empty intersection -> 0."""
        from cryptotrader.learning.evolution.idf import score_skill

        idf_table = {"rsi": 1.6, "macd": 1.2}
        query_keywords = {"news", "fed", "inflation"}
        skill_keywords = ["rsi", "macd"]
        score = score_skill(skill_keywords, query_keywords, idf_table)
        assert score == pytest.approx(0.0)

    def test_empty_skill_keywords_returns_zero(self):
        """triggers_keywords=[] yields IDF score=0 (FR-W8)."""
        from cryptotrader.learning.evolution.idf import score_skill

        idf_table = {"rsi": 1.6}
        query_keywords = {"rsi", "btc"}
        score = score_skill([], query_keywords, idf_table)
        assert score == pytest.approx(0.0)

    def test_empty_query_returns_zero(self):
        """empty query_keywords returns 0."""
        from cryptotrader.learning.evolution.idf import score_skill

        idf_table = {"rsi": 1.6}
        score = score_skill(["rsi"], set(), idf_table)
        assert score == pytest.approx(0.0)
