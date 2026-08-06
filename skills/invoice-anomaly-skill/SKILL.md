# invoice-anomaly-skill

## Purpose
Given an invoice_id (or a batch), determine whether the invoice is anomalous relative to
this company's own structured records — purchase orders, price history, payment history.
This skill never looks at contract documents; that's `contract-clause-skill`'s job.
This skill only asks: "does this look wrong compared to what we've seen before?"

## Inputs
- `invoice_id` (string) — single invoice to check, OR
- `batch_date_range` (start_date, end_date) — check all invoices in range

## Data source
Query via the `AP_SEMANTIC_VIEW` Cortex Analyst semantic view (see `sql/02_semantic_view.sql`),
joining INVOICES, PURCHASE_ORDERS, PAYMENT_HISTORY.

## Detection logic (run all three checks per invoice)

### 1. Duplicate detection
Flag if another invoice exists for the same `vendor_id` with:
- the same `invoice_amount` (exact match), AND
- `invoice_date` within 3 days of this one

Severity: **HIGH** (duplicates are unambiguous — near-zero false positive rate)

### 2. Price drift vs. PO
Compute `price_delta_pct = (invoiced_unit_price - po.unit_price) / po.unit_price * 100`
- `price_delta_pct > 15%` → **HIGH**
- `price_delta_pct` between `5%` and `15%` → **MEDIUM**
- `price_delta_pct <= 5%` → not flagged (normal variance)

### 3. Quantity mismatch vs. PO
Flag if `invoiced_quantity` differs from `po.quantity` by more than 10%.
Severity: **MEDIUM**

## Output format
Return JSON, one object per invoice checked:

```json
{
  "invoice_id": "INV0031",
  "vendor_id": "V003",
  "anomalies": [
    {
      "type": "PRICE_DRIFT",
      "severity": "HIGH",
      "evidence": "Invoiced at $47.60/unit vs PO price $40.00/unit (+19.0%)"
    }
  ],
  "clean": false
}
```

If no anomalies found, return `"anomalies": [], "clean": true`.

## Example CLI invocation
```
coco run invoice-anomaly-skill --invoice_id INV0031
coco run invoice-anomaly-skill --batch_date_range 2026-04-01,2026-07-21
```

## Notes for implementation
- Prefer expressing checks as SQL against `AP_SEMANTIC_VIEW` rather than pulling rows into
  Python and looping — this is both faster and demonstrates actual Cortex Analyst usage,
  which is part of the judging criteria ("strong use of ... Agent Skills and tools").
- Keep this skill blind to contract terms on purpose — it should only reason over internal
  transactional data. The contract cross-reference happens one layer up, in
  `risk-decision-skill`, so each skill has a single clear responsibility.
