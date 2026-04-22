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

    # BackingTrack raw audio pipeline — intentionally out of scope.
    # PyGuitarPro preserves BackingTrack.assetId so a future writer can
    # pair it with the asset; decoding audio bytes would drag in a full
    # audio stack, which is beyond the scope of #9.
    "Asset":
        "Raw audio bytes — out of scope. BackingTrack.assetId preserves "
        "the pairing for a future writer.",
    "Assets":
        "Raw audio bytes — out of scope (see Asset).",
    "EmbeddedFilePath":
        "Raw audio bytes — out of scope (see Asset).",

    # NotationPatch render metadata subtree. AT captures these to draw
    # custom percussion articulations (icons, notehead shapes, MIDI
    # input/output mapping). They have no effect on notation/playback
    # semantics; deferred until a writer PR needs round-trip fidelity
    # for custom articulation kits.
    "Articulation":
        "NotationPatch render metadata (deferred).",
    "Articulations":
        "NotationPatch render metadata (deferred).",
    "Elements":
        "NotationPatch render metadata (deferred).",
    "InputMidiNumbers":
        "NotationPatch MIDI mapping (deferred with rest of subtree).",
    "OutputMidiNumber":
        "NotationPatch MIDI mapping (deferred with rest of subtree).",
    "Noteheads":
        "NotationPatch glyph definitions (deferred).",
    "StaffLine":
        "NotationPatch glyph placement (deferred).",
    "TechniquePlacement":
        "NotationPatch glyph placement (deferred).",
    "TechniqueSymbol":
        "NotationPatch glyph definitions (deferred).",
    "Rank":
        "NotationPatch finger rank metadata (deferred).",
}


def test_every_alphatab_case_has_a_pgp_handler() -> None:
    """Every GPIF element in the snapshot must either appear as a
    quoted literal in ``gp7.py`` (= has a handler) or be explicitly
    listed in ``KNOWN_SKIPPED`` with a reason.

    If this test fails:
      - Missing handler: add a branch in ``gp7.py`` that matches the
        label as a quoted string.
      - Intentional skip: add the label to ``KNOWN_SKIPPED`` above
        with a justification comment.
    """
    snapshot = SNAPSHOT_PATH.read_text().splitlines()
    gp7_text = GP7_PATH.read_text()

    labels = [ln.strip() for ln in snapshot if ln.strip()]
    missing = []
    for label in labels:
        if label in KNOWN_SKIPPED:
            continue
        # Match the label wrapped in single or double quotes. Don't
        # use Python's `or` on re.search results (they're Match objects
        # but we only care about truthiness).
        pattern = rf'["\']{re.escape(label)}["\']'
        if not re.search(pattern, gp7_text):
            missing.append(label)

    assert not missing, (
        "alphaTab parses these GPIF elements but no handler was found "
        "in gp7.py. Either add a branch that matches the label as a "
        "quoted string, or add the label to KNOWN_SKIPPED with a "
        "rationale comment:\n  - " + "\n  - ".join(missing)
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
