# External Logic — Spark, notebooks & complex processes

OLC is [SQL-first](transformation.md), but not every transformation is one SQL statement. When a data product is built by a **Spark job**, a **notebook**, a **stored procedure**, or an existing **dbt model**, OLC doesn't make you rewrite it as declarative YAML — it **references** the real compute and keeps governing the result. The contract owns schema / quality / PII / lineage / materialization / SLO; the external code owns the transformation.

!!! abstract "Powered by"
    `logic` (inline) and `external_logic` (referenced) are **Pydantic** models. The reference runtime executes external `python` in a sandboxed subprocess (restricted builtins + timeout) and `notebook` via a Jupyter kernel. A PySpark job is just `type: python` that uses **PySpark**.

There are two ways to handle "more than one SQL statement," in order of preference.

## 1. Multi-step SQL — stay in the contract

If it's simply several SQL steps you own, list them: `transformations` runs **in order**, each a `sql:` step that sees the previous step's output. No external code needed.

```yaml
transformations:
  - sql: "SELECT *, amount * 0.2 AS tax FROM source"        # step 1
  - sql: "SELECT *, amount + tax AS gross FROM {dataset}"   # step 2 sees step 1
```

Multi-step, fully governed, still portable across engines. Reach for external logic only when the work genuinely isn't SQL.

## 2. External logic — plug in real compute

When the transformation is a *script* — PySpark, a notebook, or code that calls a stored procedure — declare `external_logic`:

```yaml
external_logic:
  type: python              # python | notebook
  path: jobs/build_trips.py # relative to the contract
  entrypoint: run           # function to call
  args: { lookback_days: 7 }
  handles_output: false     # false → return a frame, OLC materializes + governs
                            # true  → the script writes the output; OLC validates it
```

| `ExternalLogic` field | Purpose |
|---|---|
| `type` **(req)** | `python` or `notebook`. |
| `path` **(req)** | The script / notebook, relative to the contract. |
| `entrypoint` | Function to call (python). |
| `args` | Arguments passed to the entrypoint. |
| `output_path` / `output_format` | Where / how the script writes, when it handles its own output. |
| `handles_output` | `true` = the script writes the table; `false` = it returns a frame for OLC to materialize. |
| `kernel_name` | Jupyter kernel (notebook). |

### A PySpark job

A Spark job is just `type: python` — a script that uses Spark. It receives the validated data and returns a dataframe OLC then materializes and governs:

```yaml
external_logic: { type: python, path: jobs/spark_sessionize.py, entrypoint: run }
```

### A notebook

```yaml
external_logic: { type: notebook, path: notebooks/enrich_trips.ipynb, kernel_name: python3 }
```

### A stored procedure, dbt model, or existing pipeline

Two patterns:

- **Wrap it** — point `entrypoint` at a small python function that invokes the stored procedure or triggers the dbt run, and return (or write) the result.
- **Govern its output** — let your existing tool build the table, and use the contract as the *gate over the result*: set `handles_output: true` (the external build writes the data) and OLC validates schema, quality, PII, and SLO against what landed. This is the **brownfield pattern** — OLC sits beside your Spark / dbt / warehouse and *governs* it, without replacing it. See [greenfield & brownfield](../concepts/agent-workflow.md#greenfield-and-brownfield).

## Governed either way

However the data was computed — declarative SQL, a Spark job, a notebook, a stored proc — the contract's guarantees still apply:

- `handles_output: false` → the script **returns** data; OLC materializes it and enforces the contract.
- `handles_output: true` → the script **writes** the output; OLC validates the contract against it.

The compute is pluggable; the governance is the invariant.

## Scope & safety (honest)

- The reference runtime executes **`python`** and **`notebook`** external logic today. SQL stored-procedures and dbt are handled by wrapping them in a python entrypoint, or by governing their output; first-class `sql` / `dbt` types are on the roadmap.
- Python external logic runs in a **restricted sandbox** (blocks `subprocess` / `exec` / `eval` / `socket`) with a timeout — it's for *transformation* code, not arbitrary orchestration or shell-out. That's deliberate: per [scope & non-goals](../concepts/what-is-olc.md#scope-and-non-goals), OLC governs the data product; it doesn't try to be your orchestrator or compute platform. `external_logic` is the **seam** where your compute plugs into a governed contract.

## Related

- [Transformation](transformation.md) — the SQL-first, declarative ops (prefer these).
- [Materialization & Storage](materialization.md) — how the output is written and converged.
- [What is OLC? → Scope & non-goals](../concepts/what-is-olc.md#scope-and-non-goals) — why heavy compute is *referenced*, not reinvented.
