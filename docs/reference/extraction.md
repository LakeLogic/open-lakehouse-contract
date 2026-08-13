# Unstructured / LLM Extraction

OLC isn't limited to tabular sources. The `extraction` block (`ExtractionConfig`, 21 fields) turns **unstructured input — documents, transcripts, images, free text — into governed columns** using an LLM, with the same schema, quality, and PII guarantees as any other contract.

!!! abstract "Powered by"
    `ExtractionConfig` is a **Pydantic** model. Extraction calls the configured LLM through its provider SDK (**anthropic**, **openai**, …); structured output is constrained by a JSON Schema (`output_schema`) so the model returns valid rows, not prose. Preprocessing uses the right tool per modality — OCR (**tesseract** / pytesseract), speech-to-text (**whisper**), and NLP chunking (**spaCy**).

## Shape

```yaml
extraction:
  provider: anthropic
  model: claude-sonnet-5
  text_column: document_text          # the column holding raw text
  context_columns: [source_type, region]   # extra columns given to the model
  system_prompt: "You extract structured order data from support emails."
  prompt_template: "Extract fields from:\n{{ document_text }}"
  response_format: json
  output_schema:                      # the model must return rows matching this
    fields:
      - { name: order_id, type: string }
      - { name: sentiment, type: string, accepted_values: [pos, neg, neutral] }
  temperature: 0
  max_tokens: 1024
```

## Model & prompt

| Field | Purpose |
|---|---|
| `provider` / `model` | Which LLM to call. |
| `fallback_provider` / `fallback_model` | Failover model if the primary errors/limits. |
| `system_prompt` | The instruction/system message. |
| `prompt_template` | Per-row prompt; `{{ column }}` interpolates row values. |
| `text_column` | The primary unstructured input column. |
| `context_columns` | Extra columns passed as context. |
| `response_format` | Force structured output (e.g. `json`). |
| `output_schema` | The schema the response must conform to — turns free text into typed columns. |
| `temperature` / `max_tokens` | Standard decoding controls. |

## Throughput & cost guards

Extraction over many rows is bounded so a run can't blow up latency or spend:

| Field | Purpose |
|---|---|
| `batch_size` | Rows per model call/batch. |
| `concurrency` | Parallel in-flight requests. |
| `retry` | `RetryConfig` for transient LLM failures (`max_attempts`, `backoff`, `initial_delay`). |
| `max_rows_per_run` | Hard cap on rows processed per run. |
| `max_cost_per_run` | Hard spend ceiling — the run stops before exceeding it. |

!!! note "No silent caps"
    When `max_rows_per_run` / `max_cost_per_run` truncates a run, that's surfaced in the run result — a bounded run reports what it skipped rather than looking complete.

## PII before the LLM

Because prompts leave your environment, strip identifiers first:

```yaml
extraction:
  redact_pii_before_llm: true
  pii_fields: [customer_email, phone, ssn]
```

`redact_pii_before_llm` removes/masks the listed `pii_fields` **before** the prompt is built, so raw PII never reaches the provider. The field-level [`pii: true`](security.md) flags are the source of truth for what's sensitive.

## Confidence

`confidence` (`ConfidenceConfig`) attaches a confidence signal to each extracted row so low-confidence extractions can be quarantined or reviewed rather than trusted blindly — extraction output flows through the same [quality rules](quality.md) as everything else.

## Preprocessing non-text modalities

Before extraction, `preprocessing` (`PreprocessingConfig`) converts documents/media into text:

```yaml
extraction:
  preprocessing:
    content_type: pdf            # pdf | image | audio | video | text
    ocr: { lang: eng }           # scanned docs/images → text (tesseract)
    transcription: { model: whisper-1 }   # audio/video → text
    frame_extraction: { fps: 1 } # video → frames for vision models
    chunking: { max_tokens: 1000, overlap: 100 }   # split long docs (spaCy)
    file_column: file_path
    text_output_column: document_text
```

| Field | Purpose |
|---|---|
| `content_type` | The input modality. |
| `ocr` | Image/scanned-PDF text extraction. |
| `transcription` | Speech-to-text for audio/video. |
| `frame_extraction` | Sample video frames for vision models. |
| `chunking` | Split long text into overlapping windows. |
| `file_column` / `text_output_column` | Where the source file path is, and where extracted text lands. |

## Field-level extraction hints

Individual fields can carry extraction guidance in `model.fields[]`, so the "what to pull" lives next to the column:

```yaml
model:
  fields:
    - name: sentiment
      type: string
      extraction_task: "Classify the customer's sentiment."
      extraction_examples: ["'love it' → pos", "'terrible' → neg"]
```

!!! tip "Governed all the way down"
    Extracted columns are ordinary columns: they get schema validation, quality rules, PII/masking, lineage, and materialization like any other field. Unstructured input becomes a governed data product — not a side pipeline.
