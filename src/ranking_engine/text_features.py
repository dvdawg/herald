"""Lightweight text-features used by the rankers (BM25, IDF salience).

No external NLP dependencies — pure-Python tokenize + numpy math. Built for
in-pool corpora of a few hundred to a few thousand documents (candidate
windows). Larger corpora should precompute IDF once via the scheduler.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Sequence

import numpy as np

# Common English stopwords plus newsroom boilerplate that adds no signal.
_STOPWORDS = frozenset(
    """
    a an and are as at be by for from has have in is it its of on or that the
    this to was were will with you your we our they their he she them his her
    but not no can could would should has had been being do does did so if than
    then there here about also more most some any all out up over into onto via
    new news today yesterday tomorrow says said report reports update updates
    """.split()
)

# Split on word boundaries; hyphens treated as separators so "retrieval-augmented"
# tokenizes as ["retrieval", "augmented"] (standard NLP convention).
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def compute_idf(docs_tokens: Sequence[Sequence[str]]) -> Dict[str, float]:
    """Standard Robertson-Walker IDF over a corpus.

    idf(t) = log((N - df + 0.5) / (df + 0.5) + 1)
    """
    n = len(docs_tokens)
    if n == 0:
        return {}
    df: Counter = Counter()
    for tokens in docs_tokens:
        for term in set(tokens):
            df[term] += 1
    return {
        term: math.log((n - count + 0.5) / (count + 0.5) + 1.0)
        for term, count in df.items()
    }


def bm25_score(
    docs: Sequence[str],
    query_terms: Iterable[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> np.ndarray:
    """Compute normalized BM25 scores for each doc against the query.

    Returns scores in [0,1] (min-max scaled across the result set).
    """
    q = list(query_terms)
    if not q:
        return np.zeros(len(docs), dtype=np.float32)

    docs_tokens = [tokenize(d) for d in docs]
    idf = compute_idf(docs_tokens)
    doc_lens = np.array([len(t) for t in docs_tokens], dtype=np.float32)
    avgdl = float(doc_lens.mean()) if doc_lens.size and doc_lens.mean() > 0 else 1.0

    scores = np.zeros(len(docs), dtype=np.float32)
    q_terms = [t for t in q if t in idf]
    if not q_terms:
        return scores

    for i, tokens in enumerate(docs_tokens):
        tf = Counter(tokens)
        dl = doc_lens[i]
        s = 0.0
        for term in q_terms:
            f = tf.get(term, 0)
            if f == 0:
                continue
            num = f * (k1 + 1.0)
            denom = f + k1 * (1.0 - b + b * (dl / avgdl))
            s += idf[term] * (num / denom)
        scores[i] = s

    peak = float(scores.max())
    if peak > 0:
        scores = scores / peak
    return scores


def tfidf_salience(
    title: str,
    summary: str,
    idf: Dict[str, float],
    *,
    title_boost: float = 2.0,
    cap: float = 1.0,
) -> float:
    """A "is this article about something distinctive?" score in [0, cap].

    High when the article uses terms that are rare in the surrounding corpus
    (named entities, specific topics) instead of generic news boilerplate.
    Title hits count more than summary hits.
    """
    if not idf:
        return 0.0
    title_tokens = tokenize(title)
    summary_tokens = tokenize(summary)[:120]
    if not title_tokens and not summary_tokens:
        return 0.0

    title_score = sum(idf.get(t, 0.0) for t in set(title_tokens)) * title_boost
    summary_score = sum(idf.get(t, 0.0) for t in set(summary_tokens))
    total = title_score + summary_score

    # Normalize by the strongest possible signal in the corpus: pick the top-K
    # most informative terms once, sum their IDFs, and use that as the ceiling.
    # Cached on the idf dict itself to avoid recomputing per call.
    ceiling = _idf_ceiling(idf)
    if ceiling <= 0:
        return 0.0
    return float(min(total / ceiling, cap))


_idf_ceiling_cache: Dict[int, float] = {}


def _idf_ceiling(idf: Dict[str, float]) -> float:
    key = id(idf)
    cached = _idf_ceiling_cache.get(key)
    if cached is not None:
        return cached
    # Top-12 IDF values × a typical title_boost give us a generous ceiling.
    top = sorted(idf.values(), reverse=True)[:12]
    ceiling = float(sum(top))
    _idf_ceiling_cache[key] = ceiling
    return ceiling
