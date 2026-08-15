"""Example `external_logic` for `silver_trips.olc.yaml` — sessionize trips with a Spark window.

The reference runtime calls the entrypoint AFTER validation:

    run(good_df, contract=<DataContract>, engine=<"spark"|"duckdb"|"polars">, **args)

`good_df` is the validated ("good") frame in the active engine. This job adds a
`session_id` column (a new session when a rider's gap since their last completed trip
exceeds `session_gap_minutes`) and returns the frame; because the contract sets
`handles_output: false`, OLC then materializes + governs the returned frame.

Runs in LakeLogic's restricted sandbox: no `subprocess` / `shutil` / `socket`, no
`exec` / `eval`, with a timeout. It's transformation code, not orchestration.
"""

from __future__ import annotations

DEFAULT_GAP_MIN = 30


def run(
    df, *, contract=None, engine=None, session_gap_minutes: int = DEFAULT_GAP_MIN, **_
):
    """Add `session_id` to trips using a per-rider sessionization window."""
    if engine == "spark":
        from pyspark.sql import Window
        from pyspark.sql import functions as F

        w = Window.partitionBy("rider_id").orderBy("requested_at")
        prev_completed = F.lag("completed_at").over(w)
        gap_minutes = (
            F.col("requested_at").cast("long") - prev_completed.cast("long")
        ) / 60.0
        starts_new_session = (
            prev_completed.isNull() | (gap_minutes > session_gap_minutes)
        ).cast("int")
        session_index = F.sum(starts_new_session).over(w)
        return df.withColumn(
            "session_id",
            F.concat_ws("-", F.col("rider_id"), session_index.cast("string")),
        )

    # This example implements the Spark path. For DuckDB/Polars, prefer expressing the
    # same logic as a windowed SQL `transformations` step (kept fully in-contract) —
    # which is the point of the "depends on complexity" note in the contract.
    raise NotImplementedError(
        f"engine={engine!r}: this example implements the Spark path only. "
        "For non-Spark engines, use a windowed SQL transformation instead of external_logic."
    )
