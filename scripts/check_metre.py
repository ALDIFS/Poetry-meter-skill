#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诗词格律校验器（零依赖）

用法：
    python check_metre.py poem.txt --form qijue
    python check_metre.py poem.txt --form ci:浣溪沙
    echo "白日依山尽，黄河入海流。欲穷千里目，更上一层楼。" | python check_metre.py - --form auto
    python check_metre.py poem.txt --form qilv --pin "仄仄平平仄仄平,平平仄仄仄平平,..."

设计原则：
  1. 只对「有把握」的字下判断。字表未收或两读之字一律标 "?"，不臆断为平或仄。
  2. 平仄比对只严格检查二四六字（一三五不论），韵脚单列。
  3. 判「出韵」须两字韵部都已知，否则降级为提示。
"""

import argparse
import json
import os
import re
import sys

__version__ = "2.1.0"

# Windows 终端默认编码为 GBK，输出中文会炸；统一改成 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CJK = re.compile(r"[\u4e00-\u9fff]")
PUNCT = "，。；：、！？,.;:!?　 \t"

TONE_P, TONE_Z, TONE_X = "平", "仄", "?"

# ---------------------------------------------------------------- 数据加载

def load_tone_table():
    """返回 char -> ("平"/"仄", 韵部或 None, 是否两读)"""
    table = {}
    with open(os.path.join(DATA_DIR, "pingshui_ping.json"), encoding="utf-8") as f:
        data = json.load(f)
    for dept, chars in data["rhyme"].items():
        for ch in chars:
            if CJK.match(ch):
                table[ch] = ["平", dept]
    with open(os.path.join(DATA_DIR, "ze.txt"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            for ch in line.split():
                if len(ch) != 1 or not CJK.match(ch):
                    continue
                if ch in table:
                    if table[ch][0] == "平":
                        table[ch][0] = TONE_X          # 两读
                else:
                    table[ch] = ["仄", None]
    extra = os.path.join(DATA_DIR, "ping_extra.txt")
    if os.path.exists(extra):
        with open(extra, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                for ch in line.split():
                    if ch not in table:
                        table[ch] = ["平", None]        # 平声，韵部待考
    duy = os.path.join(DATA_DIR, "duyin.txt")
    if os.path.exists(duy):
        with open(duy, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                for ch in line.split():
                    if ch in table:
                        table[ch][0] = TONE_X          # 两读：保留韵部，不判平仄
                        table[ch].append("duy")
                    else:
                        table[ch] = [TONE_X, None, "duy"]
    return table


def load_cipai():
    with open(os.path.join(DATA_DIR, "cipai.json"), encoding="utf-8") as f:
        return json.load(f)["cipai"]


def find_cipai(name):
    cipai = load_cipai()
    if name in cipai:
        return name, cipai[name]
    for k, v in cipai.items():
        if name in v.get("alias", []):
            return k, v
    return None, None

# ---------------------------------------------------------------- 谱面数据

WU = ["仄仄平平仄", "平平仄仄平", "平平平仄仄", "仄仄仄平平"]
QI = ["平平仄仄平平仄", "仄仄平平仄仄平", "仄仄平平平仄仄", "平平仄仄仄平平"]

A, B, C, D = WU          # 五言：a 仄起仄收 / b 平起平收 / c 平起仄收 / d 仄起平收
a, b, c, d = QI          # 七言：a 平起仄收 / b 仄起平收 / c 仄起仄收 / d 平起平收

FORMS = {
    "wujue": [
        ("仄起首句不入韵", [A, B, C, D]),
        ("仄起首句入韵", [D, B, C, D]),
        ("平起首句不入韵", [C, D, A, B]),
        ("平起首句入韵", [B, D, A, B]),
    ],
    "wulv": [
        ("仄起首句不入韵", [A, B, C, D, A, B, C, D]),
        ("仄起首句入韵", [D, B, C, D, A, B, C, D]),
        ("平起首句不入韵", [C, D, A, B, C, D, A, B]),
        ("平起首句入韵", [B, D, A, B, C, D, A, B]),
    ],
    "qijue": [
        ("仄起首句入韵", [b, d, a, b]),
        ("仄起首句不入韵", [c, d, a, b]),
        ("平起首句入韵", [d, b, c, d]),
        ("平起首句不入韵", [a, b, c, d]),
    ],
    "qilv": [
        ("仄起首句入韵", [b, d, a, b, c, d, a, b]),
        ("仄起首句不入韵", [c, d, a, b, c, d, a, b]),
        ("平起首句入韵", [d, b, c, d, a, b, c, d]),
        ("平起首句不入韵", [a, b, c, d, a, b, c, d]),
    ],
}

FORM_WORDCOUNT = {"wujue": 20, "qijue": 28, "wulv": 40, "qilv": 56}
FORM_LABEL = {"wujue": "五绝", "qijue": "七绝", "wulv": "五律", "qilv": "七律"}

# ---------------------------------------------------------------- 解析

def parse_poem(text):
    """返回 (title, [句...])，句已去标点。"""
    text = text.replace("\r", "")
    title = ""
    m = re.search(r"《([^》]+)》", text)
    if m:
        title = m.group(1)
        text = text.replace(m.group(0), "\n")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    heads = []
    # 首行若不含标点且明显短于正文，视作诗题
    if lines and not any(p in lines[0] for p in PUNCT.replace(" ", "")) and len(lines) > 1:
        cand = "".join(CJK.findall(lines[0]))
        rest = sum(len(CJK.findall(ln)) for ln in lines[1:])
        if rest and len(cand) <= 12 and rest >= 20:
            title = title or lines[0]
            lines = lines[1:]
    for ln in lines:
        seg = re.split("[%s]" % re.escape(PUNCT.replace(" ", "")), ln)
        for s in seg:
            s = "".join(CJK.findall(s))
            if s:
                heads.append(s)
    return title, heads


def normalize_heads(heads, form):
    """若整首未断句，按谱长切分。"""
    total = sum(len(h) for h in heads)
    expected = FORM_WORDCOUNT.get(form)
    if form in FORM_WORDCOUNT and expected and total == expected and len(heads) != len(FORMS[form][0][1]):
        per = 5 if form.startswith("wu") else 7
        flat = "".join(heads)
        return [flat[i:i + per] for i in range(0, len(flat), per)]
    return heads


def resolve_tone(chars, table, pin):
    """返回 [(char, tone, dept)]；pin 为等长的 平/仄 串时优先。"""
    out = []
    for i, ch in enumerate(chars):
        if pin and i < len(pin) and pin[i] in (TONE_P, TONE_Z):
            t = pin[i]
            dept = table.get(ch, [None, None])[1]
            out.append((ch, t, dept))
        else:
            entry = table.get(ch, [TONE_X, None])
            out.append((ch, entry[0], entry[1]))
    return out

# ---------------------------------------------------------------- 校验

def strict_positions(width):
    return [1, 3] if width == 5 else [1, 3, 5]


def match_form(heads, table, form, pin_lines):
    best = None
    for label, pattern in FORMS[form]:
        if len(pattern) != len(heads):
            continue
        bad, detail = 0, []
        for idx, (head, pat) in enumerate(zip(heads, pattern)):
            if len(head) != len(pat):
                bad += 99
                break
            pin = pin_lines[idx] if pin_lines and idx < len(pin_lines) else None
            cells = resolve_tone(head, table, pin)
            for pos in strict_positions(len(pat)):
                want, got = pat[pos], cells[pos][1]
                if got == TONE_X:
                    continue
                if want != got:
                    bad += 1
                    detail.append((idx + 1, pos + 1, head[pos], want, got))
            # 韵脚平仄
            want_end, got_end = pat[-1], cells[-1][1]
            if got_end != TONE_X and want_end != got_end:
                bad += 1
                detail.append((idx + 1, len(pat), head[-1], want_end, got_end))
        if best is None or bad < best[0]:
            best = (bad, label, pattern, detail)
    return best


CI_GROUPS = {
    "一东": "第一部", "二冬": "第一部",
    "三江": "第二部", "七阳": "第二部",
    "四支": "第三部", "五微": "第三部", "八齐": "第三部", "十灰": "第三部",
    "六鱼": "第四部", "七虞": "第四部",
    "九佳": "第五部",
    "十一真": "第六部", "十二文": "第六部", "十三元": "第六部",
    "十四寒": "第七部", "十五删": "第七部", "一先": "第七部",
    "二萧": "第八部", "三肴": "第八部", "四豪": "第八部",
    "五歌": "第九部", "六麻": "第十部",
    "八庚": "第十一部", "九青": "第十一部", "十蒸": "第十一部",
    "十一尤": "第十二部", "十二侵": "第十三部",
    "十三覃": "第十四部", "十四盐": "第十四部", "十五咸": "第十四部",
}


def _dept_key(dept, group_fn):
    if not dept:
        return None
    return group_fn.get(dept, dept) if group_fn else dept


def check_rhyme(heads, table, rhyme_marks=None, pattern=None, group_fn=None, segmented=False):
    """韵脚检查。(句号, 字, 平仄, 平水韵部, 归并后韵部, 韵符)"""
    issues, cautions = [], []
    if rhyme_marks:
        positions = [(i, j, mk) for i, row in enumerate(rhyme_marks)
                     for j, mk in enumerate(row) if mk in "△▲"]
    elif pattern:
        positions = [(i, len(p) - 1, "△") for i, p in enumerate(pattern) if p[-1] == TONE_P]
    else:
        positions = [(i, len(h) - 1, "△") for i, h in enumerate(heads)
                     if table.get(h[-1], [TONE_X])[0] == TONE_P]

    feet = []
    for i, j, mk in positions:
        if i >= len(heads) or j >= len(heads[i]):
            continue
        ch = heads[i][j]
        entry = table.get(ch, [TONE_X, None])
        tone, dept = entry[0], entry[1]
        feet.append((i + 1, ch, tone, dept, _dept_key(dept, group_fn), mk))

    segments, cur = [], []
    for f in feet:
        if cur and segmented and f[5] != cur[-1][5]:
            segments.append(cur)
            cur = []
        cur.append(f)
    if cur:
        segments.append(cur)

    for seg in segments:
        known = [f for f in seg if f[4]]
        groups = list(dict.fromkeys(f[4] for f in known))
        if len(groups) > 1:
            body = [f[4] for f in known[1:]]
            if len(known) > 2 and len(set(body)) == 1 and known[0][4] != body[0]:
                cautions.append("首句韵脚「%s」属%s，余皆%s，此为孤雁出群（借韵），唐人容许"
                                % (known[0][1], known[0][3], body[0]))
            else:
                detail = "、".join("%s(%s)" % (f[1], f[3] or f[4]) for f in known)
                issues.append("韵脚分属 %d 处，出韵 —— %s" % (len(groups), detail))

    depts = list(dict.fromkeys(f[3] for f in feet if f[3]))
    return feet, depts, issues, cautions


LONE_PING_TYPES = ("平平仄仄平", "仄仄平平仄仄平")


def oddities(heads, table, pattern=None):
    """孤平、三平尾、三仄尾、重字。孤平只就「平平仄仄平」类句式而论。"""
    notes = []
    for i, h in enumerate(heads):
        cells = [table.get(ch, [TONE_X])[0] for ch in h]
        is_lone_type = pattern is not None and i < len(pattern) and pattern[i] in LONE_PING_TYPES
        if is_lone_type:
            inner = cells[:-1]
            if all(c != TONE_X for c in inner) and inner.count(TONE_P) <= 1:
                notes.append("第%d句犯孤平（%s）：除韵脚外仅余一个平声字" % (i + 1, h))
        tail = cells[-3:]
        if tail == [TONE_P] * 3:
            notes.append("第%d句三平尾（%s），近体大忌" % (i + 1, h))
        if tail == [TONE_Z] * 3:
            notes.append("第%d句三仄尾（%s），古人偶有，终是弱笔" % (i + 1, h))
    flat = "".join(heads)
    dup = sorted({c for c in flat if flat.count(c) > 1})
    return notes, dup


def check_ci(heads, table, name, spec):
    ge = spec["ge"]
    issues = []
    if len(heads) != len(ge):
        issues.append("句数不符：%s 正体 %d 句，实得 %d 句" % (name, len(ge), len(heads)))
        return None, issues, [], []
    pattern, marks = [], []
    bad, detail = 0, []
    for idx, (h, g) in enumerate(zip(heads, ge)):
        if len(h) != len(g):
            issues.append("第%d句字数不符：应为 %d 字（%s），实得 %d 字" % (idx + 1, len(g), g, len(h)))
            continue
        row, mk = "", ""
        cells = resolve_tone(h, table, None)
        want_of = {"○": TONE_P, "△": TONE_P, "●": TONE_Z, "▲": TONE_Z}
        for pos, sym in enumerate(g):
            row += cells[pos][1]
            mk += sym if sym in "△▲" else "·"
            want = want_of.get(sym)
            if want:
                got = cells[pos][1]
                if got != TONE_X and got != want:
                    bad += 1
                    detail.append((idx + 1, pos + 1, h[pos], want, got))
        pattern.append(row)
        marks.append(mk)
    # 韵脚
    feet, uniq, rhyme_issues, rhyme_notes = check_rhyme(
        heads, table, marks, group_fn=CI_GROUPS, segmented=(spec["rhyme"] == "换韵"))
    issues += rhyme_issues
    issues = issues
    if spec["rhyme"] == "仄":
        for f in feet:
            if f[2] == TONE_P:
                issues.append("韵脚「%s」为平声，此调宜用仄韵" % f[1])
    elif spec["rhyme"] == "平":
        for f in feet:
            if f[2] == TONE_Z:
                issues.append("韵脚「%s」为仄声，此调宜用平韵" % f[1])
    if spec["rhyme"] == "仄" and not any(f[3] for f in feet):
        rhyme_notes.append("此为仄韵，字表仅收平声韵部，韵脚是否同部须查《词林正韵》")
    return (bad, detail), issues, feet, uniq, rhyme_notes

# ---------------------------------------------------------------- 输出

def render(title, form_label, label, heads, table, detail, feet, depts, issues, notes, dup, coverage, missing):
    out = []
    head = "《%s》" % title if title else ""
    out.append("%s 体裁：%s%s" % (head, form_label, (" · " + label) if label else ""))
    out.append("")
    for i, h in enumerate(heads):
        row = "".join(table.get(c, [TONE_X])[0] for c in h)
        out.append("  %s  %s" % (h, row))
    out.append("")
    if detail:
        out.append("平仄不合（二四六字与韵脚）：")
        for ln, pos, ch, want, got in detail:
            out.append("  第%d句第%d字「%s」应%s，实为%s" % (ln, pos, ch, want, got))
    elif label:
        out.append("平仄：合律")
    if feet:
        feet_desc = "、".join("%s(%s%s)" % (f[1], f[2], "/" + f[3] if f[3] else "") for f in feet)
        out.append("韵脚：%s" % feet_desc)
        if depts:
            out.append("韵部：%s" % "、".join(depts))
    duy = [c for c in "".join(heads)
           if len(table.get(c, [])) > 2 and table[c][2] == "duy"]
    if duy:
        out.append("两读字：%s（平仄随义而变，脚本未判，须按语境定音）"
                   % "".join(dict.fromkeys(duy)))
    if missing:
        out.append("字表未收：%s（%d 字，占 %.0f%%），未作判定，须人工定平仄或改用 --pin"
                   % ("".join(missing), len(missing), 100 - coverage))
    if notes:
        out.append("慎处：")
        for n in notes:
            out.append("  " + n)
    if dup:
        out.append("重字：%s（有意复叠则不论）" % "".join(dup))
    if issues:
        out.append("硬伤：")
        for i in issues:
            out.append("  " + i)
    else:
        out.append("硬伤：无")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="诗词格律校验（近体诗 / 常用词牌）")
    ap.add_argument("path", nargs="?", default="-", help="诗稿文件，- 表示标准输入")
    ap.add_argument("--version", action="version", version="check_metre %s" % __version__)
    ap.add_argument("--list", action="store_true", help="列出支持的体裁与词牌")
    ap.add_argument("--form", default="auto", help="wujue|qijue|wulv|qilv|ci:词牌名|auto")
    ap.add_argument("--pin", default="", help="手工平仄串，逗号或空格分句，如 仄仄平平仄,平平仄仄平")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.list:
        print("近体诗（--form）")
        for key, variants in FORMS.items():
            print("  %-7s %s，%d 字，%d 式" % (key, FORM_LABEL[key], FORM_WORDCOUNT[key], len(variants)))
        print("\n词牌（--form ci:词牌名）")
        for name, spec in load_cipai().items():
            print("  %-5s %2d 字  %s" % (name, sum(len(g) for g in spec["ge"]), spec["rhyme"]))
        print("\n退出码：0 校验完成；2 输入或体裁无法解析")
        return 0

    text = sys.stdin.read() if args.path == "-" else open(args.path, encoding="utf-8").read()
    table = load_tone_table()
    title, heads = parse_poem(text)
    if not heads:
        print("未解析到诗句。", file=sys.stderr)
        return 2

    form = args.form
    if form == "auto":
        total = sum(len(h) for h in heads)
        lens = [len(h) for h in heads]
        cands = []
        for key, variants in FORMS.items():
            if FORM_WORDCOUNT[key] == total:
                for label, pat in variants:
                    score = sum(1 for a, b in zip([len(p) for p in pat], lens) if a == b)
                    cands.append((score, "jinti", key))
                break
        for name in load_cipai():
            _, spec = find_cipai(name)
            glens = [len(g) for g in spec["ge"]]
            if sum(glens) != total:
                continue
            score = sum(1 for a, b in zip(glens, lens) if a == b)
            cands.append((score, "ci", name))
        cands = [c for c in cands if c[0] * 2 > len(lens)]     # 句长须过半吻合
        if not cands:
            print("无法自动判定体裁（共 %d 字，句长 %s），请显式指定 --form。"
                  % (total, "/".join(map(str, lens))), file=sys.stderr)
            return 2
        cands.sort(key=lambda c: (c[0], c[1] == "jinti"), reverse=True)
        kind, name = cands[0][1], cands[0][2]
        if kind == "jinti":
            # 近体必押平韵；若双向句全为仄收，判为词
            ends = [heads[i][-1] for i in range(1, len(heads), 2)]
            tones = [table.get(c, [TONE_X])[0] for c in ends]
            if tones and all(t == TONE_Z for t in tones):
                alt = [c for c in cands if c[1] == "ci"]
                if alt:
                    kind, name = alt[0][1], alt[0][2]
        form = name if kind == "jinti" else "ci:%s" % name

    pin_lines = [p for p in re.split(r"[,，\s]+", args.pin.strip()) if p] if args.pin else None

    if form.startswith("ci:"):
        name = form[3:]
        real, spec = find_cipai(name)
        if not spec:
            print("未收录词牌「%s」。已收录：%s" % (name, "、".join(load_cipai())), file=sys.stderr)
            return 2
        heads = normalize_heads(heads, real)
        res, issues, feet, depts, notes = check_ci(heads, table, real, spec)
        detail = res[1] if res else []
        label = "正体（%s）" % (spec["rhyme"] if spec["rhyme"] == "换韵" else spec["rhyme"] + "韵")
        extra, dup = oddities(heads, table)
        notes = notes + extra
    else:
        heads = normalize_heads(heads, form)
        if len(heads) != len(FORMS[form][0][1]):
            print("句数与 %s 不符：应 %d 句，实得 %d 句。"
                  % (FORM_LABEL[form], len(FORMS[form][0][1]), len(heads)), file=sys.stderr)
            return 2
        best = match_form(heads, table, form, pin_lines)
        bad, label, pattern, detail = best
        feet, depts, issues, rhyme_notes = check_rhyme(heads, table, pattern=pattern)
        notes, dup = oddities(heads, table, pattern)
        fatal = [n for n in notes if "三平尾" in n]
        notes = rhyme_notes + [n for n in notes if n not in fatal]
        issues += fatal
        if bad >= 99:
            print("句长与所判体裁不符，无法比对谱面。", file=sys.stderr)
            return 2
        if bad > 0 and bad <= 2:
            notes.append("有不拘处 %d 字，若为拗救（如三拗四救）可通，须逐处核" % bad)

    flat = "".join(heads)
    known = sum(1 for c in flat if c in table)          # 两读字仍在表内，计入覆盖
    coverage = known * 100.0 / max(len(flat), 1)
    missing = [c for c in dict.fromkeys(flat) if c not in table]

    if args.json:
        print(json.dumps({
            "title": title, "form": form, "label": label, "heads": heads,
            "deviations": [{"line": d[0], "pos": d[1], "char": d[2], "want": d[3], "got": d[4]} for d in detail],
            "rhyme_feet": [{"line": f[0], "char": f[1], "tone": f[2], "dept": f[3], "group": f[4]} for f in feet],
            "depts": depts, "issues": issues, "cautions": notes,
            "repeated": dup, "coverage": round(coverage, 1), "unknown_chars": missing,
        }, ensure_ascii=False, indent=2))
        return 0

    form_label = ("词·" + form[3:]) if form.startswith("ci:") else FORM_LABEL.get(form, "")
    print(render(title, form_label, label, heads, table,
                 detail, feet, depts, issues, notes, dup, coverage, missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
