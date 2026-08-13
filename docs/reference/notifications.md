# Notifications

When something the contract cares about happens — rows quarantined, an SLO breached, a schema change, a run failure — OLC can emit a notification. Notifications (`Notification`) are declared inline wherever an event originates: on `quarantine`, and alongside SLOs.

!!! abstract "Powered by"
    `Notification` is a **Pydantic** model. The reference runtime delivers to each channel with the appropriate transport — SMTP for email, an incoming-webhook `POST` (via **requests**) for Slack/Teams/webhooks. Message bodies are rendered from templates (Jinja-style) with a per-event context.

## Shape

```yaml
quarantine:
  enabled: true
  notifications_enabled: true
  notifications:
    - type: slack
      target: "#data-alerts"
      on_events: [quarantine, dataset_rule_failure]
      subject_template: "⚠️ {{ contract }} quarantined {{ count }} rows"
      message_template: "{{ count }} rows failed {{ rule }} in {{ table }} (run {{ run_id }})."
    - type: email
      targets: ["data-oncall@example.com", "owner@example.com"]
      on_events: [slo_breach, run_failure]
      body_template_file: "templates/slo_breach.html"
```

## Fields

| `Notification` field | Purpose |
|---|---|
| `type` | Channel: `slack`, `email`, `teams`, `webhook`, … |
| `target` | A single destination (channel, address, URL). |
| `targets` | Multiple destinations. |
| `on_events` | Which events trigger this notification (see below). |
| `subject_template` / `subject_template_file` | Subject line — inline or from a file. |
| `message_template` / `message_template_file` | Short message body — inline or file. |
| `body_template` / `body_template_file` | Rich/HTML body — inline or file. |
| `template_context` | Extra key/values merged into the render context. |

## Events

`on_events` scopes a notification to the things worth paging about. Typical events:

| Event | Fires when |
|---|---|
| `quarantine` | Rows were quarantined this run. |
| `dataset_rule_failure` | A dataset-level rule failed. |
| `slo_breach` | A freshness / availability / row-count SLO was missed. |
| `schema_change` | Incoming schema diverged from the contract. |
| `run_failure` | The run errored out. |
| `run_success` | The run completed (for heartbeats). |

## Templating

Subject/message/body are templates rendered with an event context — the contract, table, rule, counts, run id, and anything in `template_context`. Inline templates are convenient; `*_template_file` variants keep long/HTML bodies out of the YAML:

```yaml
notifications:
  - type: email
    targets: ["governance@example.com"]
    on_events: [schema_change]
    subject_template: "Schema change in {{ domain }}/{{ system }}: {{ contract }}"
    body_template_file: "templates/schema_change.html"
    template_context: { runbook: "https://wiki/runbooks/schema-change" }
```

## Where notifications attach

- **Quarantine** — `quarantine.notifications[]`, gated by `notifications_enabled` and `strict_notifications`. See [Validation & Quality](quality.md#quarantine).
- **SLOs** — a breach of any [service level](slo.md) can raise a notification.
- **Control plane** — in the [LakeLogic](https://lakelogic.org) runtime, these same events also drive incidents, dashboards, and Zeus (agentic diagnosis) — the contract declares *what* to alert on; the platform decides *how far* to escalate.

!!! tip "Keep secrets out of the contract"
    Webhook URLs and SMTP credentials are environment configuration, not contract content. Reference them via env/secret settings on the runtime; the contract only names the *channel* and *event*, so it stays safe to commit and share.
