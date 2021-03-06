#!/usr/bin/env python3

import shutil
import tempfile
import unittest
from collections import Counter
from os import path
from unittest.mock import Mock, patch

from pytorch_translate.research.unsupervised_morphology import bpe


txt_content = ["123 124 234 345", "112 122 123 345", "123456789", "123456 456789"]


class TestBPE(unittest.TestCase):
    def test_vocab_init(self):
        bpe_model = bpe.BPE()

        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__ = mock_open
            mock_open.return_value.__iter__ = Mock(return_value=iter(txt_content))
            bpe_model._init_vocab(txt_path="no_exist_file.txt")

            vocab_items = Counter()
            for vocab_entry, freq in bpe_model.current_train_data:
                items = vocab_entry.split()
                for item in items:
                    vocab_items[item] += freq

            assert vocab_items[bpe_model.eow_symbol] == 11
            assert vocab_items["3"] == 7
            assert len(vocab_items) == 10
            assert "12" not in vocab_items
            assert "123" not in vocab_items

    def test_best_candidate(self):
        bpe_model = bpe.BPE()

        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__ = mock_open
            mock_open.return_value.__iter__ = Mock(return_value=iter(txt_content))
            bpe_model._init_vocab(txt_path="no_exist_file.txt")

            assert bpe_model.get_best_candidate(num_cpus=3) == ("1", "2")

    def test_bpe_merge(self):
        bpe_model = bpe.BPE()

        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__ = mock_open
            mock_open.return_value.__iter__ = Mock(return_value=iter(txt_content))
            bpe_model._init_vocab(txt_path="no_exist_file.txt")

            # Trying merging a candidate that does not exist.
            vocab_size = bpe_model.merge_candidate_into_vocab(
                candidate=("3", "1"), num_cpus=3
            )
            assert vocab_size == 10

            # Trying merging a candidate that does exists.
            vocab_size = bpe_model.merge_candidate_into_vocab(
                candidate=("2", "3"), num_cpus=3
            )
            assert vocab_size == 11

            # Trying merging a candidate that does exists. Entry "3" should remove
            # from vocab.
            vocab_size = bpe_model.merge_candidate_into_vocab(
                candidate=("3", "4"), num_cpus=3
            )
            assert vocab_size == 11

            # Trying merging a candidate that does not exist.
            vocab_size = bpe_model.merge_candidate_into_vocab(
                candidate=("3", bpe_model.eow_symbol), num_cpus=3
            )
            assert vocab_size == 11

    def test_merge_pattern(self):
        pattern1 = bpe.BPE.get_merge_pattern("c c")
        assert pattern1.sub("cc", "x|x?^d@@ c c ^d") == "x|x?^d@@ cc ^d"

        pattern2 = bpe.BPE.get_merge_pattern("^d@ @c")
        assert (
            pattern2.sub("^d@@c", "^d@ @cx|x? ^d@ @c c ^d") == "^d@ @cx|x? ^d@@c c ^d"
        )

        pattern3 = bpe.BPE.get_merge_pattern("x| x")
        assert (
            pattern3.sub("x|x", "^d@ @c x| x ?^d@ @c c ^d") == "^d@ @c x|x ?^d@ @c c ^d"
        )

    def test_build_vocab(self):
        bpe_model = bpe.BPE()

        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__ = mock_open
            mock_open.return_value.__iter__ = Mock(return_value=iter(txt_content))

            # Trying to build a vocab more than the possible size
            vocab_size = bpe_model.build_vocab(
                txt_path="no_exist_file.txt", vocab_size=20, num_cpus=3
            )
            # Asserting that we go back to the original size (number of word types.)
            assert vocab_size == 9
            assert bpe_model.max_bpe_len == 9 + len(bpe_model.eow_symbol)

        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__ = mock_open
            mock_open.return_value.__iter__ = Mock(return_value=iter(txt_content))
            # Trying to build a vocab with an acceptable size.
            vocab_size = bpe_model.build_vocab(
                txt_path="no_exist_file.txt", vocab_size=12, num_cpus=3
            )
            # asserting that the size is as expected.
            assert vocab_size == 12
            assert bpe_model.max_bpe_len == len(bpe_model.eow_symbol)

    def test_segment_word(self):
        bpe_model = bpe.BPE()

        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__ = mock_open
            mock_open.return_value.__iter__ = Mock(return_value=iter(txt_content))

            bpe_model.build_vocab(
                txt_path="no_exist_file.txt", vocab_size=12, num_cpus=3
            )
            assert bpe_model.segment_word("1234") == ["12", "34", bpe_model.eow_symbol]

            # Giving unknown character sequence
            assert bpe_model.segment_word("12634") == [
                "12",
                "6",
                "34",
                bpe_model.eow_symbol,
            ]

    def test_segment_file(self):
        bpe_model = bpe.BPE()

        tmp_dir = tempfile.mkdtemp()
        input_file, output_file = (
            path.join(tmp_dir, "test.in"),
            path.join(tmp_dir, "test1.out"),
        )

        with open(input_file, "w", encoding="utf-8") as writer:
            writer.write("\n".join(txt_content))
        bpe_model.build_vocab(txt_path=input_file, vocab_size=12, num_cpus=3)

        output = []
        for line in txt_content:
            cur_line_output = []
            for word in line.strip().split():
                cur_line_output.append(" ".join(bpe_model.segment_word(word)))
            output.append(" ".join(cur_line_output))
            output.append("\n")
        expected_output = "".join(output).strip()

        bpe_model.segment_txt(input_path=input_file, output_path=output_file)
        model_output = open(output_file, "r", encoding="utf-8").read().strip()
        assert expected_output == model_output

        shutil.rmtree(tmp_dir)
