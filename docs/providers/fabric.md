# Microsoft Fabric

**Engine:** Spark · **Format:** Delta · **Storage:** OneLake (schema-enabled Lakehouse) · **Status:** ◑ Validated & deploy-ready — assign a Fabric capacity to run.

!!! info "Assign a capacity, then run"
    Microsoft Fabric is **capacity-based**: every Fabric workload runs on an **F-SKU (or trial) capacity assigned to the workspace**. That assignment is a normal Fabric prerequisite the customer provides — so this provider ships **validated and deploy-ready** rather than pre-run: the RideFlow (like Uber) contracts are ported **verbatim**, schema-validated, and the OneLake + REST deploy path is wired. Attach a capacity and the same contracts run unchanged — **Spark on Delta into OneLake**, both already proven live on other providers.

**Reference data mesh lakehouse:** [`lakelogic-microsoft-fabric-data-mesh-lakehouse`](https://github.com/LakeLogic/lakelogic-microsoft-fabric-data-mesh-lakehouse) — the ported RideFlow mesh lives there: the OneLake + REST (`az` token) deploy path, and the OneLake Delta tables it materializes once a capacity is attached.

## The same contract

The RideFlow contracts are ported **verbatim** from the data-mesh repo — no Fabric-specific edits. Backend choices:

```yaml
materialization:
  strategy: merge
  format: delta          # OneLake Delta in a schema-enabled Lakehouse
```

## Special configuration

How the LakeLogic framework adapts to this backend (handled for you):

- **Schema-enabled Lakehouse:** tables live under schemas (domain-per-schema), matching the mesh layout; OneLake **Files** holds the landing CSVs.
- **Next step to go Live:** attach a Fabric capacity and run the deploy path once to promote this from ◑ to ✅.
