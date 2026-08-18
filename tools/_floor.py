"""A floor on how little an extractor is allowed to produce.

Why this exists (issue #111): both extractors swallow every per-model failure as
a warning, and their ``main()`` used to write the output file and exit 0 no
matter how many models survived. A full outage is loud, so it is not the
dangerous case. The dangerous case is upstream *restructuring*: pages return
200, the markup no longer matches the selectors, every model is logged as a
warning, and the scheduled ``schema-refresh.yml`` run stays green while
committing a near-empty schema. Downstream repos build on that file, so the
failure surfaces somewhere else, later, with nothing in the diff to blame.

The count of extracted models is therefore an assertion, not a log line.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# A run that keeps at least this fraction of the previous run's models is
# treated as an upstream edit; anything below it is treated as a broken
# extraction. 0.9 leaves room for the handful of models Blesta actually removes
# in a release (6 of the current 63) while failing any restructuring large
# enough to matter. --allow-shrink is the escape hatch when the drop is real,
# so the cost of the floor being too tight is one flag, not a blocked refresh.
MIN_RETAINED_FRACTION = 0.9


class ExtractionFloorError(RuntimeError):
    """Raised when an extraction produced too few models to be trusted.

    Carries an operator-facing message: whoever is reading a red run should not
    have to open the source to learn what happened or what to do next.
    """


def previous_model_count(path: Path) -> int | None:
    """Read ``metadata.model_count`` from a previously written schema file.

    :param path: Path the extractor is about to overwrite.
    :return: The previous run's model count, or ``None`` when there is no
        readable previous schema to compare against.
    """
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None

    if not isinstance(data, dict):
        return None
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    count = metadata.get("model_count")
    if isinstance(count, int) and not isinstance(count, bool) and count > 0:
        return count
    return None


def enforce_model_floor(
    model_count: int,
    *,
    source: str,
    output: Path,
    baseline: int | None = None,
    allow_shrink: bool = False,
    fraction: float = MIN_RETAINED_FRACTION,
) -> None:
    """Fail the run when too few models were extracted to trust the result.

    :param model_count: Models the run actually extracted.
    :param source: Human-readable description of what was being extracted.
    :param output: File the run was about to write.
    :param baseline: Previous run's model count, or ``None`` when unavailable.
        With no baseline only the zero floor applies.
    :param allow_shrink: Skip the proportional floor (never the zero floor)
        because the operator has confirmed the drop is a real upstream removal.
    :param fraction: Fraction of ``baseline`` that must survive.
    :raises ExtractionFloorError: When the run is below a floor.
    """
    if model_count == 0:
        raise ExtractionFloorError(
            f"Extracted 0 models from {source}. Nothing was written, so "
            f"{output} still holds the last good schema.\n"
            "Zero models almost never means upstream has none — it means the "
            "pages answered 200 with markup the parser no longer recognises, "
            "and every model was skipped as a warning.\n"
            "What to do: open the source above in a browser, compare its "
            "structure against the selectors in tools/extract_schema.py "
            "(parse_model_list, parse_class_page) or the docblock patterns in "
            "tools/extract_plugin_schema.py, fix them, then re-run with "
            "--dry-run until the model count looks right."
        )

    if baseline is None or allow_shrink:
        return

    minimum = math.ceil(baseline * fraction)
    if model_count < minimum:
        raise ExtractionFloorError(
            f"Extracted {model_count} models from {source}, below the floor of "
            f"{minimum} ({fraction:.0%} of the {baseline} in {output}). Nothing "
            "was written, so that file still holds the last good schema.\n"
            "A drop this size is usually a parser that has fallen behind the "
            "upstream markup, not a deletion: models that fail to parse are "
            "skipped as warnings, so they leave no other trace.\n"
            "What to do: re-run with --dry-run and diff the model names against "
            f"{output} to see which ones vanished. If they really are gone "
            "upstream, re-run with --allow-shrink to accept the smaller schema."
        )
