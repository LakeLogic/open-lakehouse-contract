"""Deterministic text extraction (no LLM): parse `temperature=<int>` and
`status=<word>` out of a free-text `note` column into structured fields.
Engine-agnostic — the same rules run on Polars, DuckDB, and Spark frames."""

from typing import Any, Dict, Optional

_TEMP = r"temperature=(\d+)"
_STATUS = r"status=(\w+)"


def run(
    good_df: Any,
    links: Optional[Dict[str, Any]] = None,
    engine: str = "polars",
    **kwargs: Any,
) -> Any:
    mod = type(good_df).__module__
    if mod.startswith("pyspark"):
        from pyspark.sql import functions as F

        return good_df.withColumn(
            "temperature", F.regexp_extract("note", _TEMP, 1).cast("int")
        ).withColumn("status", F.regexp_extract("note", _STATUS, 1))
    if mod.startswith("polars"):
        import polars as pl

        df = good_df.collect() if isinstance(good_df, pl.LazyFrame) else good_df
        return df.with_columns(
            pl.col("note").str.extract(_TEMP, 1).cast(pl.Int64).alias("temperature"),
            pl.col("note").str.extract(_STATUS, 1).alias("status"),
        )
    # pandas
    return good_df.assign(
        temperature=good_df["note"].str.extract(_TEMP)[0].astype("Int64"),
        status=good_df["note"].str.extract(_STATUS)[0],
    )
