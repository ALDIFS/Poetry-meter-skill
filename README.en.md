# poetry-craft

*[中文说明见 README.md](README.md)*

A skill package for writing and revising Tang regulated verse and Song ci: nine working principles, a six-step process, two reference documents, and a **dependency-free** metre checker you can actually run.

`SKILL.md` is written for the agent. This file is for humans.

## The problem

Language models produce two reliable failure modes with classical Chinese verse.

They get metre wrong while believing they got it right — a poem that looks like a regulated octave, announced as "合律", with a broken parallelism, an out-of-rhyme foot, and a triple-level ending. These errors are **decidable**. Decidable checks belong in code, not in a model's intuition.

And they fall into pastiche: stacked ornament, crowded imagery, an uplifting final line. That cannot be decided by a program, only held down by principles and a checklist.

This repository splits the two: `scripts/check_metre.py` for the first, the nine principles in `SKILL.md` and the fault table in `references/poetics.md` for the second.

## Relationship to 2.0.0

Built on the `skill.md` of [ALDIFS/Poetry-meter-skill](https://github.com/ALDIFS/Poetry-meter-skill) 2.0.0, keeping its five-part structure and the nine principles, while filling in what was missing: all sixteen tone patterns (2.0.0 had eight), the complete thirty Pingshui rhyme categories (2.0.0 listed only the first fifteen, missing 阳/庚/尤/先 entirely), eleven ci patterns with full notation (2.0.0 had four), the four types of metrical rescue, and an actual checker instead of an output template. Full comparison in [CHANGELOG.md](CHANGELOG.md).

## Checker

Python 3.9+, no install, no dependencies.

```bash
python scripts/check_metre.py poem.txt --form auto
python scripts/check_metre.py poem.txt --form qijue
python scripts/check_metre.py poem.txt --form ci:浣溪沙
python scripts/check_metre.py --list
```

It verifies line count and line length, tone at positions 2/4/6 of every line, rhyme category of each foot (Pingshui rhymes for regulated verse, Cilin Zhengyun groups for ci), isolated-level lines (孤平), triple-level endings (三平尾), and repeated characters. Mixed-rhyme ci patterns are checked segment by segment. `--json` gives structured output; `--pin` lets you supply tones by hand when a character is outside the bundled tables.

## Known limits

The character tables are a **common-character subset**, not a complete rhyme book: roughly 1500 level-tone characters assigned to the thirty Pingshui categories, 1400 oblique-tone characters, and 60 polyphonic characters listed separately. Characters absent from all tables are marked `?` and reported — never silently assumed oblique. Polyphonic characters are never judged. Only eleven ci patterns are included, in their standard form; long-form patterns are deliberately omitted because their variants are numerous and a wrong pattern would produce confident nonsense. Rhyme category of oblique-tone ci is not verified. Parallelism and overall quality are out of scope by design.

## Install as a skill

```bash
git clone https://github.com/ALDIFS/poetry-craft.git ~/.workbuddy/skills/poetry-craft
```

## Development

```bash
python -m unittest discover -s tests -v
```

CI runs on Ubuntu, Windows and macOS against Python 3.9 and 3.12.

## License

MIT. See [LICENSE](LICENSE).

This version continues `ALDIFS/Poetry-meter-skill` 2.0.0: its five-part structure and nine principles are kept, with the tone patterns, rhyme tables, ci patterns and checker completed or added. The prose is rewritten.
