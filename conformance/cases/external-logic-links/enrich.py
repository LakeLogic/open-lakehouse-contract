"""Conformance external-logic step: left-join the source trips frame onto the
`drivers` reference link, engine-agnostically. Returns the enriched frame."""

from typing import Any, Dict, Optional


def run(
    good_df: Any,
    links: Optional[Dict[str, Any]] = None,
    engine: str = "polars",
    **kwargs: Any,
) -> Any:
    links = links or {}
    drivers = links.get("drivers")
    if drivers is None:
        raise ValueError("external_logic expected a 'drivers' link but received none.")

    mod = type(good_df).__module__
    if mod.startswith("pyspark"):
        return good_df.join(drivers, on="driver_id", how="left")
    import polars as pl

    s = good_df.collect() if isinstance(good_df, pl.LazyFrame) else good_df
    d = drivers.collect() if isinstance(drivers, pl.LazyFrame) else drivers
    return s.join(d, on="driver_id", how="left")
