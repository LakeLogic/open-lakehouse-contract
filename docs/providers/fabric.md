# Microsoft Fabric

**Engine:** Spark · **Format:** Delta · **Storage:** OneLake (schema-enabled Lakehouse) · **Status:** ◑ Static-validated — the contracts and the OneLake deploy path are validated, but a live run is pending (no Fabric capacity provisioned to execute against yet).

!!! warning "Honest status"
    Unlike the other ✅ Live providers, Fabric has **not been executed end-to-end on a live capacity**. The RideFlow (like Uber) contracts were ported verbatim and statically validated, and the deploy mechanics (OneLake + REST) are wired — but there was no Fabric capacity available to do a real run. This page describes the intended path; treat it as validated-but-not-yet-run until a capacity is attached.

## The same contract

The RideFlow contracts are ported **verbatim** from the data-mesh repo — no Fabric-specific edits. Backend choices:

```yaml
materialization:
  strategy: merge
  format: delta          # OneLake Delta in a schema-enabled Lakehouse
```

## Run it (intended)

Deploy via REST / OneLake using an `az` access token, into a **schema-enabled Lakehouse** with a OneLake **Files** landing zone:

```bash
# Reference repo: lakelogic-microsoft-fabric-data-mesh-lakehouse
az login
python deploy/fabric_deploy.py     # OneLake upload + REST job registration via az token
```

## What it would materialize

The full six-domain medallion as OneLake Delta tables in a schema-enabled Lakehouse, governed identically to the other backends.

## Special configuration

- **Schema-enabled Lakehouse:** tables live under schemas (domain-per-schema), matching the mesh layout; OneLake **Files** holds the landing CSVs.
- **Auth:** deploy is driven by an `az` access token (REST + OneLake), no workspace secret embedded.
- **Next step to go Live:** attach a Fabric capacity and run the deploy path once to promote this from ◑ to ✅.
