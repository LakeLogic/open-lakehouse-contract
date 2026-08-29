# OLC-N-004 — drift *inside* a struct

## What this case pins

The contract declares `payload: struct<a:int,b:string>`. The incoming struct has
only `a`. The member `b` is gone.

The case pins that such a row **must not land in the accepted set**. It does not
pin *how* that is enforced: quarantining the row and refusing the run both
satisfy it (`assertions.refusal_conforms: true`).

## Why the expectation is a judgement call

There are three defensible answers to "a struct lost a declared member":

1. **Quarantine the row** — consistent with how every other contract breach is
   handled in this corpus, and it keeps the batch alive.
2. **Refuse the run** — a struct's shape is schema-level, not row-level: if one
   row's struct is missing `b`, every row's is, so quarantining row-by-row is
   theatre. Spark does this.
3. **Accept silently** — what DuckDB and Polars currently do. Not defensible:
   the whole point of declaring `struct<a:int,b:string>` is to be told when the
   data stops matching it.

(1) and (2) are both honest; (3) is the bug. **The case therefore accepts either
(1) or (2)** and fails only on (3).

An earlier version of this case pinned (1) alone, which recorded Spark as a
"known gap" for choosing (2). That ranked the only engine that detects the drift
as the deviant one, next to two engines that miss it entirely — precisely
backwards. Pinning the invariant (*the bad row must not be accepted*) rather than
the mechanism states what the spec actually requires.

## Current engine behaviour

| Engine | Behaviour | Verdict |
|---|---|---|
| DuckDB | accepts the row | silent data-quality hole |
| Polars | accepts the row | silent data-quality hole |
| Spark  | aborts the run (`DATATYPE_MISMATCH`) | **conforms** — enforcement via (2) |

Only DuckDB and Polars are recorded in `KNOWN_GAPS`. Spark passes. Do not "fix"
Spark by making it match DuckDB — that would trade the one correct behaviour for
the bug.

## How the harness expresses this

`assertions.refusal_conforms: true` tells the comparator that a run refusal is a
conforming outcome for this case. It is deliberately narrow:

- It is opt-in per case, so it cannot quietly soften the rest of the corpus.
- It cannot rescue a row that was **accepted** — silent acceptance still fails.

This is distinct from `assertions.expects_error`, which means "this contract must
be rejected at load time" and requires a deliberately invalid contract
(`test_all_case_contracts_are_strict_valid`). Here the contract is valid; it is
the *data* that breaches it.
