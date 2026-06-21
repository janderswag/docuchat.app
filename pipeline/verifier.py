"""M2-6 — Mechanical span-level citation verification (D-19). The milestone keystone.

For each claim the answer asserts, mechanically (no LLM) check that its cited span
overlaps an actually-retrieved chunk's char offsets on that chunk's page text. A
claim whose span does not overlap a real retrieved chunk is REJECTED before display
and surfaced explicitly (never silently dropped). Displayed filename + page are
chunk-derived (D-38) and the verified span's page offsets are returned.

Overlap criterion (deterministic): a claim is verified iff the NORMALIZED cited
span is a substring of the NORMALIZED text of the chunk the claim points to. Each
grounding chunk's ``text`` is exactly its page slice ``page_text[char_start:char_end]``,
so a substring match is, by construction, an overlap within [char_start, char_end];
the matched location is mapped back to raw offsets and reported as page offsets
(``char_start + local``). Normalization follows the M2-1/M2-2 contract — decode HTML
entities (``&quot;`` ...), strip backslash-escaped quotes (``\\"`` -> ``"``), collapse
whitespace, de-wrap ``-\\n`` to ``-`` keeping the hyphen, drop quote characters,
lowercase — applied symmetrically to span and chunk so PDF reflow and the model's
quote-escaping (M2-8a: F-014 ``\\"``, F-016 ``&quot;``) do not cause a false reject.
The added decoding only removes characters from the comparison; it can recover a
truthful escaped span but can never make a fabricated span match — the verifier still
fails conservatively.
"""

import html

from answering import REFUSAL

_QUOTES = "\"'“”‘’"


def _norm_map(text):
    """Normalize per the M2-1/M2-2 contract, keeping a map from each normalized char
    back to its raw index in ``text`` (so a match can be reported as raw offsets).

    Phase 1 de-escapes the raw text — decode HTML entities and drop backslashes that
    escape a quote — pairing every resulting char with the raw index it came from.
    Phase 2 applies the reflow/quote/case contract on those pairs, so the offset map
    stays anchored to raw indices even after a multi-char entity collapses (M2-8a)."""
    pairs = []  # (char, raw_index)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n and text[i + 1] in _QUOTES:
            i += 1; continue  # drop the escaping backslash; the quote is dropped below
        if c == "&":
            j = text.find(";", i + 1)
            if 0 < j - i <= 10:
                ent = text[i:j + 1]
                dec = html.unescape(ent)
                if dec != ent:  # a real entity — map each decoded char to the entity start
                    for d in dec:
                        pairs.append((d, i))
                    i = j + 1; continue
        pairs.append((c, i)); i += 1

    out, omap, p, m = [], [], 0, len(pairs)
    while p < m:
        c, idx = pairs[p]
        if c == "-" and p + 1 < m and pairs[p + 1][0] == "\n":
            out.append("-"); omap.append(idx); p += 2; continue
        if c in _QUOTES:
            p += 1; continue
        if c.isspace():
            out.append(" "); omap.append(idx); p += 1
            while p < m and pairs[p][0].isspace():
                p += 1
            continue
        out.append(c.lower()); omap.append(idx); p += 1
    return "".join(out), omap


def locate_span(chunk_text, span):
    """Raw [start, end) of ``span`` within ``chunk_text`` (normalized), or None."""
    nchunk, omap = _norm_map(chunk_text)
    nspan, _ = _norm_map(span)
    nspan = nspan.strip()
    if not nspan:
        return None
    k = nchunk.find(nspan)
    if k < 0:
        return None
    return omap[k], omap[k + len(nspan) - 1] + 1


def verify_answer(answer_text, grounding_chunks):
    """Mechanically verify every asserted claim. Returns
    {citations: [verified, chunk-derived + page offsets], rejected_claims: [...]}.
    """
    if REFUSAL in answer_text:
        return {"citations": [], "rejected_claims": []}

    from answering import _extract_and_resolve  # lazy: avoids an import cycle

    claims = _extract_and_resolve(answer_text, grounding_chunks)
    seen, verified, rejected = set(), [], []
    for cl in claims:
        target, span = cl["target"], cl["span"]
        if not span.strip():
            rejected.append({"span": span, "asserted_chunk": cl["chunk_hint"],
                             "reason": "citation has no verifiable span"})
            continue
        if target is None:
            rejected.append({"span": span, "asserted_chunk": cl["chunk_hint"],
                             "reason": "cited span not found in any retrieved chunk"})
            continue
        loc = locate_span(target["text"], span)
        if loc is None:
            rejected.append({"span": span, "asserted_chunk": cl["chunk_hint"],
                             "reason": f"cited span does not overlap chunk {target['chunk_id']} "
                                       f"(page {target['page_number']}, offsets "
                                       f"{target['char_start']}..{target['char_end']})"})
            continue
        key = (target["source_filename"], target["page_number"], target["chunk_id"])
        if key in seen:
            continue
        seen.add(key)
        verified.append({
            "filename": target["source_filename"],
            "page": target["page_number"],
            "chunk_id": target["chunk_id"],
            "span": span,
            "char_start": target["char_start"] + loc[0],
            "char_end": target["char_start"] + loc[1],
        })
    return {"citations": verified, "rejected_claims": rejected}
