"""GPIF reader parity gate.

Guards against silent regressions: if alphaTab's ``GpifParser.ts``
adds a new ``case '<Foo>'`` and the PyGuitarPro port doesn't pick
up a corresponding handler, this test fires.

Mechanics:

  1. ``tests/gp7_at_case_labels.txt`` is a frozen snapshot of every
     GPIF XML element alphaTab's switch statements match on, taken
     from ``packages/alphatab/src/importer/GpifParser.ts``. It is
     updated manually when we re-sync against a new alphaTab release.
  2. The gate asserts every snapshot label is referenced as a quoted
     string somewhere in ``gp7.py`` — the PGP reader.
  3. Labels we intentionally don't handle live in the ``KNOWN_SKIPPED``
     allowlist below with explicit reasons, so the test stays green
     while the gaps are visible and reviewable.

When you add a new alphaTab-parity handler:
  - Add the quoted literal to ``gp7.py`` (the gate will detect it).
  - Do NOT add the label to ``KNOWN_SKIPPED``.

When you add a new intentional skip:
  - Add the label to ``KNOWN_SKIPPED`` with a short reason comment
    directly above the entry.

When alphaTab ships a new release:
  - Regenerate the snapshot by running the shell one-liner in
    ``regenerate_snapshot()`` below against a fresh alphaTab checkout.
  - Re-run this test; either add handlers or add skips for new items.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).parent.parent
SNAPSHOT_PATH = Path(__file__).parent / "gp7_at_case_labels.txt"
GP7_PATH = REPO / "src" / "guitarpro" / "gp7.py"
MODELS_PATH = REPO / "src" / "guitarpro" / "models.py"


# Labels alphaTab parses but PyGuitarPro intentionally does not handle.
# Each entry must have a reason comment; review the list whenever the
# snapshot is regenerated.
KNOWN_SKIPPED: dict[str, str] = {
    # AT parses these "no-op" cases — it reads the XML but doesn't
    # populate any model field, so skipping in PGP matches AT's
    # actual behaviour.
    "HopoDestination":
        "AT parses but does not set a field — hammer-pull "
        "destination is auto-calculated from HopoOrigin.",
    "WhammyBarExtend":
        "AT skips with comment 'not clear what this is used for'.",

    # NotationPatch / InstrumentSet Articulation subtree — all 10
    # labels (Articulation, Articulations, Elements, InputMidiNumbers,
    # OutputMidiNumber, Noteheads, StaffLine, TechniqueSymbol,
    # TechniquePlacement) are handled by the PercussionArticulation
    # parser in gp7.py. See PR #40.
}


def test_every_alphatab_case_has_a_pgp_handler() -> None:
    """Every GPIF element in the snapshot must be referenced somewhere
    in the reader chain, or listed in ``KNOWN_SKIPPED`` with a reason.

    Three match paths (all legitimate):

      1. **Quoted literal in gp7.py** — normal sibling / property
         branch (e.g. ``if name == "Fret":``).
      2. **Quoted literal in models.py** — when the label names an
         enum *value token* that's mapped via a module-level dict
         (e.g. the rasgueado tokens in ``_RASGUEADO_MAP``, chord-
         ``Ring``/``Rank`` in ``_read_chord_diagrams``'s inline map).
      3. **Enum member name in models.py** — when the reader does a
         dynamic ``gp.MusicFontSymbol[token]`` lookup against an enum
         whose members are named verbatim after the GPIF tokens
         (noteheads, technique symbols, technique placements).

    If this test fails:
      - Missing handler: add a branch / enum member / dict entry.
      - Intentional skip: add the label to ``KNOWN_SKIPPED`` above
        with a justification comment.
    """
    snapshot = SNAPSHOT_PATH.read_text().splitlines()
    gp7_text = GP7_PATH.read_text()
    models_text = MODELS_PATH.read_text()

    labels = [ln.strip() for ln in snapshot if ln.strip()]
    missing = []
    for label in labels:
        if label in KNOWN_SKIPPED:
            continue
        # Match 1: quoted literal in either source file.
        quoted_pattern = rf'["\']{re.escape(label)}["\']'
        if re.search(quoted_pattern, gp7_text):
            continue
        if re.search(quoted_pattern, models_text):
            continue
        # Match 2: enum member name in models.py (dynamic lookup
        # via ``EnumName[token]``). Enum member definitions take the
        # form ``<identifier> = <int>`` at the start of a line
        # (with indent), so require a word-boundary match that
        # starts at the beginning of a line (ignoring leading
        # whitespace).
        if re.search(rf'^\s+{re.escape(label)}\s*=\s*\d', models_text, re.MULTILINE):
            continue
        missing.append(label)

    assert not missing, (
        "alphaTab parses these GPIF elements but no handler was found "
        "in gp7.py or models.py. Either add a handler (branch / dict "
        "entry / enum member), or add the label to KNOWN_SKIPPED with "
        "a rationale comment:\n  - " + "\n  - ".join(missing)
    )


def test_known_skipped_labels_are_still_in_snapshot() -> None:
    """Protect against stale entries in ``KNOWN_SKIPPED``. When
    alphaTab removes a case, we should review whether the PGP
    equivalent is still relevant — don't keep a skip note for a case
    that no longer exists.
    """
    snapshot = {ln.strip() for ln in SNAPSHOT_PATH.read_text().splitlines() if ln.strip()}
    stale = sorted(label for label in KNOWN_SKIPPED if label not in snapshot)
    assert not stale, (
        "These labels are in KNOWN_SKIPPED but no longer appear in the "
        "alphaTab case snapshot — probably removed upstream. Delete the "
        "skip entry after confirming:\n  - " + "\n  - ".join(stale)
    )


def regenerate_snapshot() -> None:
    """Not a test. One-liner commentary for maintainers updating the
    snapshot against a new alphaTab release::

        grep -oE "case '[A-Z][A-Za-z0-9]*'" \\
          packages/alphatab/src/importer/GpifParser.ts \\
          | sed -E "s/case '(.+)'/\\1/" | sort -u > tests/gp7_at_case_labels.txt

    Then rerun this module's tests and resolve any new missing labels
    (either with a handler or with a ``KNOWN_SKIPPED`` entry).
    """
    ...
