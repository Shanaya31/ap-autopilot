# risk-decision-skill

## Purpose
The orchestration and decision layer. Takes the outputs of `invoice-anomaly-skill` and
`contract-clause-skill` for a given invoice, combines them into a single risk verdict,
takes the appropriate action, and writes a full audit trail. This is the skill that turns
"we found some issues" into "here is what happens next" — the piece most hackathon
projects skip.

## Inputs
- `invoice_id` (string)
- `anomaly_result` — output of `invoice-anomaly-skill` for this invoice
- `contract_result` — output of `contract-clause-skill` for this invoice's vendor

## Decision logic

Compute a risk tier from the combined evidence:

| Condition | Tier | Action |
|---|---|---|
| `no_contract_on_file == true` | **ESCALATE** | No baseline to verify against — always route to a human, never auto-approve |
| `contract_expired == true` | **ESCALATE** | Vendor is being paid under lapsed terms — compliance/legal exposure |
| Any anomaly with severity `HIGH` (duplicate, or price_drift > 15%, or price_term_mismatch) | **ESCALATE** | Clear, high-confidence problem |
| Any anomaly with severity `MEDIUM`, no `HIGH` present | **HOLD** | Worth a look, not urgent |
| `anomalies == []` AND `mismatch_check` all false | **APPROVE** | Clean invoice, no action needed |

## Actions per tier

- **APPROVE**: write to `AUDIT_LOG` with `decision = 'APPROVE'`, one-line reasoning, no
  further output. This is the silent happy path — most invoices should land here.
- **HOLD**: write to `AUDIT_LOG` with `decision = 'HOLD'`, and generate a short memo
  (3-5 sentences) naming the specific discrepancy, quoting the actual numbers/clause, and
  suggesting the concrete next step (e.g. "confirm with vendor whether pricing was
  updated without a contract amendment").
- **ESCALATE**: same as HOLD but tag urgency and address the memo to "AP Manager review
  required" — this is the case a human must look at before any payment proceeds.

## Output format
```json
{
  "invoice_id": "INV0031",
  "decision": "ESCALATE",
  "risk_tier_reason": "Price drift 19.0% (HIGH) + contract confirms mismatch",
  "memo": "Invoice INV0031 from Vertex IT Services bills IT Support Hours at $47.60/unit. The signed contract (C003, effective through 2026-09-15) states a contracted rate of $42.00/unit for this line item -- a $5.60 (13.3%) overcharge relative to contract terms, and a 19.0% overcharge relative to the original PO. Recommend holding payment pending vendor confirmation of whether a price change was formally negotiated; no amendment is on file.",
  "audit_log_entry_written": true
}
```

## Orchestration flow (top-level CoCo CLI workflow)

```
1. intake invoice_id (or batch)
2. call invoice-anomaly-skill(invoice_id)          -> anomaly_result
3. call contract-clause-skill(vendor_id, invoice_context)  -> contract_result
4. call risk-decision-skill(invoice_id, anomaly_result, contract_result)
5. write decision + both raw evidence blobs to AUDIT_LOG (VARIANT columns)
6. if HOLD or ESCALATE: print/return the memo; if APPROVE: log only, no output noise
```

### Error branch (required — this is what judges mean by "handles decision branches")
If step 3 returns `no_contract_on_file: true`, **skip straight to ESCALATE** — do not
attempt further reasoning, since there is nothing to reason against. This is the one
branch that must never fall through to APPROVE by default.

## Example CLI invocation (top-level, runs the full chain)
```
coco run ap-autopilot-workflow --batch_date_range 2026-04-01,2026-07-21
```
Expected output for a ~50-invoice batch: mostly silent APPROVE logging, a handful of
printed HOLD memos, 1-2 printed ESCALATE memos (the expired-contract and no-contract
cases should always surface here).

## Notes for implementation
- Keep the memo generation prompt strict about citing actual numbers from the evidence —
  a memo that says "there may be a pricing discrepancy" is weak; a memo that says
  "$47.60/unit vs. contracted $42.00/unit, a 13.3% overcharge" is the demo-winning version.
- The `AUDIT_LOG` table is your entire "solution completeness" story for judging — every
  decision needs both raw evidence blobs attached (VARIANT columns), not just the final
  verdict, so a reviewer can see the full reasoning chain.
