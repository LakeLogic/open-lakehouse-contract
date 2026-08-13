Validate this repository's Open Lakehouse Contracts against the JSON Schema — structural
check only, no runtime required.

Run in the shell:

    olc validate $ARGUMENTS

(If `olc` is not installed, run `python scripts/validate.py $ARGUMENTS` instead.)

Then:
- If everything is OK, list which files passed.
- If any file FAILED, read each reported `location: message`, open the offending
  `*.olc.yaml`, and edit it to satisfy the schema at
  `schema/open-lakehouse-contract.schema.json`. Re-run until it passes.
