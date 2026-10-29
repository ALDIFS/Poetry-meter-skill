#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_metre.py 的回归测试。

运行：python -m unittest discover -s tests -v
不依赖任何第三方库，Python 3.9 起可用。
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "check_metre.py")

WUJUE = "白日依山尽，黄河入海流。欲穷千里目，更上一层楼。"
WULV = ("国破山河在，城春草木深。感时花溅泪，恨别鸟惊心。"
        "烽火连三月，家书抵万金。白头搔更短，浑欲不胜簪。")
QIJUE = "秦时明月汉时关，万里长征人未还。但使龙城飞将在，不教胡马度阴山。"
QILV = ("风急天高猿啸哀，渚清沙白鸟飞回。无边落木萧萧下，不尽长江滚滚来。"
        "万里悲秋常作客，百年多病独登台。艰难苦恨繁霜鬓，潦倒新停浊酒杯。")
HUANXISHA = ("一曲新词酒一杯，去年天气旧亭台。夕阳西下几时回。"
             "无可奈何花落去，似曾相识燕归来。小园香径独徘徊。")
YUMEIREN = ("春花秋月何时了，往事知多少。小楼昨夜又东风，故国不堪回首月明中。"
            "雕栏玉砌应犹在，只是朱颜改。问君能有几多愁，恰似一江春水向东流。")
SHENGZHAZI = ("去年元夜时，花市灯如昼。月上柳梢头，人约黄昏后。"
              "今年元夜时，月与灯依旧。不见去年人，泪湿春衫袖。")


def run(poem, *args):
    """以 UTF-8 字节喂给子进程，避免 Windows 控制台编码干扰。"""
    proc = subprocess.run(
        [sys.executable, SCRIPT, "-"] + list(args),
        input=poem.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


class TestJinti(unittest.TestCase):
    """近体诗：四体各一首名篇，应判合律。"""

    CASES = [
        ("wujue", WUJUE),
        ("wulv", WULV),
        ("qijue", QIJUE),
        ("qilv", QILV),
    ]

    def test_all_forms_pass(self):
        for form, poem in self.CASES:
            with self.subTest(form=form):
                code, out, _ = run(poem, "--form", form)
                self.assertEqual(code, 0)
                self.assertIn("平仄：合律", out)
                self.assertIn("硬伤：无", out)

    def test_rhyme_dept_resolved(self):
        code, out, _ = run(QIJUE, "--form", "qijue")
        self.assertEqual(code, 0)
        self.assertIn("十五删", out)

    def test_tone_error_detected(self):
        bad = QIJUE.replace("秦时明月", "秦日明月")
        code, out, _ = run(bad, "--form", "qijue")
        self.assertEqual(code, 0)
        self.assertIn("应平，实为仄", out)

    def test_rhyme_error_detected(self):
        bad = QIJUE.replace("度阴山", "度阴川")
        code, out, _ = run(bad, "--form", "qijue")
        self.assertEqual(code, 0)
        self.assertIn("出韵", out)

    def test_sanpingwei_detected(self):
        bad = "白日依山尽，黄河入海流。欲穷千里目，更上青云楼。"
        code, out, _ = run(bad, "--form", "wujue")
        self.assertEqual(code, 0)
        self.assertIn("三平尾", out)

    def test_line_count_mismatch(self):
        code, out, err = run(QIJUE + "月落乌啼霜满天。", "--form", "qijue")
        self.assertEqual(code, 2)
        self.assertIn("句数", err)


class TestCi(unittest.TestCase):
    """词：平韵、仄韵、换韵三类各测一首。"""

    CASES = [
        ("ci:浣溪沙", HUANXISHA, "浣溪沙"),
        ("ci:虞美人", YUMEIREN, "虞美人"),
        ("ci:生查子", SHENGZHAZI, "生查子"),
    ]

    def test_all_forms_pass(self):
        for form, poem, name in self.CASES:
            with self.subTest(name=name):
                code, out, _ = run(poem, "--form", form)
                self.assertEqual(code, 0)
                self.assertIn("平仄：合律", out)
                self.assertIn("硬伤：无", out)
                self.assertIn(name, out)

    def test_ci_rhyme_uses_cilin_groups(self):
        """鹧鸪天「钟/红/风/逢/同/中」分属一东二冬，词林正韵内可通押。"""
        poem = ("彩袖殷勤捧玉钟，当年拚却醉颜红。舞低杨柳楼心月，歌尽桃花扇底风。"
                "从别后，忆相逢，几回魂梦与君同。今宵剩把银釭照，犹恐相逢是梦中。")
        code, out, _ = run(poem, "--form", "ci:鹧鸪天")
        self.assertEqual(code, 0)
        self.assertNotIn("出韵", out)

    def test_auto_detect_ci(self):
        code, out, _ = run(SHENGZHAZI, "--form", "auto")
        self.assertEqual(code, 0)
        self.assertIn("词·生查子", out)

    def test_unknown_cipai(self):
        code, _, err = run(HUANXISHA, "--form", "ci:不存在的词牌")
        self.assertEqual(code, 2)
        self.assertIn("未收录", err)


class TestInterface(unittest.TestCase):
    """命令行契约：JSON、手工平仄、自描述。"""

    def test_json_output(self):
        code, out, _ = run(QIJUE, "--form", "qijue", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["form"], "qijue")
        self.assertEqual(len(data["heads"]), 4)
        self.assertEqual(data["issues"], [])
        self.assertGreater(data["coverage"], 85.0)
        self.assertTrue(data["rhyme_feet"])

    def test_pin_overrides_dictionary(self):
        code, out, _ = run(WUJUE, "--form", "wujue",
                           "--pin", "仄仄平平仄,平平仄仄平,仄平平仄仄,仄仄仄平平")
        self.assertEqual(code, 0)
        self.assertIn("平仄：合律", out)

    def test_list_forms(self):
        proc = subprocess.run([sys.executable, SCRIPT, "--list"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0)
        out = proc.stdout.decode("utf-8", "replace")
        for name in ("wujue", "qijue", "wulv", "qilv", "浣溪沙", "蝶恋花"):
            self.assertIn(name, out)

    def test_version(self):
        proc = subprocess.run([sys.executable, SCRIPT, "--version"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0)

    def test_empty_input_rejected(self):
        code, _, err = run("", "--form", "qijue")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
