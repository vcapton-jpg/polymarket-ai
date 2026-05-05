"""Boilerplate stripping for Polymarket market descriptions.

Audit follow-up 2026-05-05 (M1). The `_BOILERPLATE_RE` constant lived
in `app/workers/tasks_ingestion.py` purely as a definition — that
module never used it locally. Both call sites
(`compose_market_v1`, `compose_market_v2`) live in
`app/processing/text_composers.py`, which had to do the layer-inverted
`from app.workers.tasks_ingestion import _BOILERPLATE_RE`. The
`processing` layer is meant to sit BELOW `workers`, not above. A
rename of the symbol on the `workers` side would silently break
text-composer rendering at runtime; that's the kind of shake-and-pray
coupling we want to retire.

Now `processing.market_text_normalize.BOILERPLATE_RE` is the canonical
home and `text_composers` imports from a peer module. `tasks_ingestion`
keeps a backward-compat alias `_BOILERPLATE_RE` re-exporting from here
for the (audit-confirmed-zero) chance some external script imports the
private name.
"""

from __future__ import annotations

import re

# Pattern matches Polymarket-shaped boilerplate disclaimers that are
# semantically noise for retrieval/embedding purposes:
#   - "This market will resolve …"
#   - "If the result is not known …"
#   - "If there is ambiguity …"
#   - "This market pertains to / includes / covers …"
# The (?i) flag makes it case-insensitive; each alternative ends at
# the first sentence boundary (., newline, or end of string).
BOILERPLATE_RE: re.Pattern[str] = re.compile(
    r"(?i)("
    r"this market will resolve\b.*?(?:\.\s*|\n|$)"
    r"|if the results? (?:is|are) not known\b.*?(?:\.\s*|\n|$)"
    r"|if there is ambiguity\b.*?(?:\.\s*|\n|$)"
    r"|this market (?:pertains to|includes|covers)\b.*?(?:\.\s*|\n|$)"
    r")"
)
