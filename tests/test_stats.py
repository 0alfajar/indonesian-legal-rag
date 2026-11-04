"""Offline tests for the statistics and experiment helpers behind the technical report."""

import json
import unittest
from pathlib import Path

import numpy as np

from legal_rag.evaluation import compare
from legal_rag.experiments import lexical_overlap, lodo_cv, select_weight
from legal_rag.stats import bootstrap_ci, holm, paired_permutation_test, per_question, spearman, summarize
from legal_rag.storage import fingerprint

ROOT = Path(__file__).resolve().parents[1]


class StatsTests(unittest.TestCase):
    def test_per_question_scores_match_definitions(self):
        scores = per_question([1, 2, None, 6])
        np.testing.assert_allclose(scores["mrr@5"], [1, .5, 0, 0])
        np.testing.assert_allclose(scores["hit@3"], [1, 1, 0, 0])

    def test_bootstrap_ci_brackets_mean_and_collapses_for_constants(self):
        low, high = bootstrap_ci(np.array([0., 1.] * 20))
        self.assertLess(low, .5)
        self.assertGreater(high, .5)
        self.assertEqual(bootstrap_ci(np.ones(10)), (1.0, 1.0))
        self.assertEqual(summarize([1, 1])["hit@1"]["ci95"], (1.0, 1.0))

    def test_permutation_test_separates_signal_from_noise(self):
        clear = paired_permutation_test(np.ones(30), np.zeros(30))
        self.assertLess(clear["p_value"], .001)
        self.assertEqual((clear["wins"], clear["losses"]), (30, 0))
        balanced = paired_permutation_test(np.array([1., 0.] * 15), np.array([0., 1.] * 15))
        self.assertGreater(balanced["p_value"], .9)

    def test_holm_is_monotone_and_capped(self):
        adjusted = holm({"a": .01, "b": .04, "c": .03})
        self.assertAlmostEqual(adjusted["a"], .03)
        self.assertAlmostEqual(adjusted["c"], .06)
        self.assertAlmostEqual(adjusted["b"], .06)  # never below a smaller p's adjusted value
        self.assertEqual(holm({"a": .9, "b": .8})["a"], 1.0)

    def test_spearman(self):
        self.assertAlmostEqual(spearman(np.arange(5), np.arange(5) ** 2), 1.0)
        self.assertAlmostEqual(spearman(np.arange(5), -np.arange(5)), -1.0)
        self.assertTrue(np.isnan(spearman(np.ones(4), np.arange(4))))

    def test_compare_reports_holm_corrected_paired_tests(self):
        runs = {name: {"results": [{"rank": r} for r in ranks]} for name, ranks in
                {"served": [1] * 20, "a": [None] * 20, "b": [1] * 20}.items()}
        result = compare(runs, "served", ("a", "b"))
        self.assertLess(result["a"]["p_holm"], .01)
        self.assertEqual(result["b"]["mean_difference"], 0)


class ExperimentTests(unittest.TestCase):
    def test_weight_selection_and_cross_validation_never_see_the_held_out_fold(self):
        questions = [{"expected_doc": d} for d in ["A"] * 4 + ["B"] * 4]
        sweep = {0.2: [1, 1, 1, 1, None, None, None, None],   # best on A only
                 0.8: [None, None, None, None, 1, 1, 1, 1]}   # best on B only
        result = lodo_cv(questions, sweep)
        folds = {f["held_out"]: f["selected_weight"] for f in result["folds"]}
        self.assertEqual(folds, {"A": 0.8, "B": 0.2})        # chosen on the other document
        self.assertEqual(result["cross_validated"]["mrr@5"]["mean"], 0.0)
        self.assertAlmostEqual(result["optimism_mrr@5"], 0.5)
        self.assertEqual(select_weight(sweep, np.ones(8, bool)), 0.8)  # tie -> closest to served 0.7

    def test_lexical_overlap_ignores_stopwords(self):
        self.assertEqual(lexical_overlap("Apa itu upah minimum?", "Upah minimum provinsi"), 1.0)
        self.assertEqual(lexical_overlap("Apa itu upah lembur?", "Upah minimum"), 0.5)


class DatasetTests(unittest.TestCase):
    def test_test_set_is_frozen_and_disjoint_from_dev(self):
        read = lambda name: json.loads((ROOT / "data/evaluation" / name).read_text(encoding="utf-8"))  # noqa: E731
        test, dev = read("test.json"), read("dev.json")
        self.assertEqual(fingerprint(test),
                         "c52627c7389c41020e874fec317e54fe0a846804c69fdbd3f01acc9051985c8e",
                         "test.json changed after pre-registration; record an erratum instead")
        key = lambda q: (q["expected_doc"], str(q["expected_pasal"]))  # noqa: E731
        self.assertFalse({key(q) for q in test} & {key(q) for q in dev})
        sampled = read("test_articles.json")["articles"]
        self.assertEqual({key(q) for q in test}, {(a["doc_id"], a["pasal"]) for a in sampled})


if __name__ == "__main__":
    unittest.main()
