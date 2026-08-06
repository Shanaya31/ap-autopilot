# cli/ — Python orchestration layer

This is the layer that turns your SQL data engineering work into the
end-to-end agentic workflow the hackathon judges are looking for.

## Architecture (why it's split this way)

Snowflake trial accounts block `AI_PARSE_DOCUMENT`, Cortex Search embeddings,
and `CORTEX.COMPLETE`. Rather than fight that, responsibilities are split
cleanly by what each layer is actually good at:

- **Snowflake** — deterministic data engineering and rule evaluation
  (`INVOICE_ANOMALY_RESULTS`, `AP_REVIEW_QUEUE`, `CONTRACT_CLAUSE_ANALYSIS`,
  `CONTRACT_STATUS` already compute severity and recommended action)
- **Python** (`decision_skill.py`) — combines those pre-computed results and
  enforces the one safety-critical override in code: a vendor with **no
  contract on file** always escalates, regardless of what any table says
- **Gemini** (`gemini_reasoner.py`) — explains a decision already made in
  plain language; it never makes the decision itself

This is a single-source-of-truth design: business rules live only in SQL,
never duplicated in Python.

## Setup

```bash
pip install -r requirements.txt --break-system-packages

export SNOWFLAKE_ACCOUNT=your_account_identifier
export SNOWFLAKE_USER=your_username
export SNOWFLAKE_PASSWORD=your_password
export SNOWFLAKE_WAREHOUSE=AP_AUTOPILOT_WH
export SNOWFLAKE_DATABASE=AP_AUTOPILOT
export SNOWFLAKE_SCHEMA=CORE
export GOOGLE_API_KEY=your_gemini_key
```

Test the Snowflake connection first, in isolation:
```bash
python snowflake_client.py
```
Should print a row count from `VENDORS`. If this fails, fix it before
touching anything else — every other file depends on this working.

## ⚠️ Column names — check before running

`invoice_anomaly_skill.py` and `contract_clause_skill.py` assume column
names like `INVOICE_ID`, `VENDOR_ID`, `SEVERITY`, `CONTRACT_STATUS`,
`CONTRACT_END`. These are based on the table names you built earlier, but if
your actual columns are named slightly differently (e.g. lowercase, or
`RISK_SEVERITY` instead of `SEVERITY`), you'll need to adjust the `SELECT`
statements and the `.get(...)` lookups in `decision_skill.py` to match. This
is meant to be a quick find-and-replace, not a rewrite — the query shape is
already correct, only the exact names might need a tweak.

Quick way to check your actual columns:
```sql
DESCRIBE TABLE AP_REVIEW_QUEUE;
DESCRIBE TABLE CONTRACT_CLAUSE_ANALYSIS;
DESCRIBE TABLE CONTRACT_STATUS;
```

## Commands

```bash
python cli.py review-invoice INV0007       # single invoice, full report
python cli.py scan-open-invoices           # full batch, one command
python cli.py inspect-contract V003        # contract detail for one vendor
```

## Testing order (recommended)

1. `python snowflake_client.py` — connectivity only
2. `python invoice_anomaly_skill.py INV0007` — raw query, check the JSON looks right
3. `python contract_clause_skill.py V003` — same, for contract data
4. `python decision_skill.py INV0007 V003` — combined decision, no Gemini yet
5. `python gemini_reasoner.py` — standalone test with fake data, confirms Gemini key works
6. `python cli.py review-invoice INV0007` — full pipeline, single invoice
7. `python cli.py scan-open-invoices` — full batch, this is your demo command

Test step 4 specifically against:
- **V003 or V007** (seeded price mismatch) — should return HOLD or ESCALATE
- **V009 or V010** (expired contract) — should always return ESCALATE
- A vendor with genuinely no contract row at all, if you have one — should
  return ESCALATE with `no_contract_on_file: true`, never APPROVE
