# contract-clause-skill

## Purpose
Given a vendor_id, retrieve that vendor's current contract from the unstructured document
store, extract the terms that matter for AP reconciliation, and — when given an invoice —
determine whether the invoice's stated terms conflict with what the contract actually says.
This is the "reasoning over unstructured data" half of the system.

## Inputs
- `vendor_id` (string) — required
- `invoice_context` (object, optional) — `{invoiced_unit_price, line_item, invoice_date}`.
  If provided, the skill also returns a mismatch verdict, not just raw extraction.

## Data source
`CONTRACT_SEARCH_SVC` Cortex Search service (see `sql/03_stage_and_search.sql`), searching
over parsed contract text keyed by `vendor_id`.

## Steps

1. **Retrieve**: query `CONTRACT_SEARCH_SVC` filtered to `vendor_id`, retrieve the most
   relevant contract chunk(s) — the pricing schedule and renewal/expiration clauses
   specifically, since those are the two things AP cares about.
2. **Extract**: from the retrieved text, extract:
   - `unit_pricing` — line item → contracted price (may be stated as a table, in prose,
     or as an amendment referencing an older base contract — handle all three; contracts
     in this dataset are deliberately structured differently from each other)
   - `expiration_date` — when the contract lapses
   - `renewal_type` — auto-renew vs. requires renegotiation
   - `penalty_clause` — late payment penalty terms, if present
   - `price_increase_notice_period` — how much notice is required before a price change
     takes effect
3. **Cross-reference** (only if `invoice_context` provided):
   - Is today's date (or `invoice_date`) past `expiration_date`? → flag `CONTRACT_EXPIRED`
   - Does `invoiced_unit_price` match the contracted price for that `line_item`
     (within 1% tolerance)? If not → flag `PRICE_TERM_MISMATCH` with both values quoted
   - If no contract found at all for this `vendor_id` → flag `NO_CONTRACT_ON_FILE`
     (this is the error branch — treat as maximum severity, not a silent pass)

## Output format
```json
{
  "vendor_id": "V003",
  "contract_found": true,
  "expiration_date": "2026-09-15",
  "renewal_type": "requires_renegotiation",
  "extracted_pricing": {"IT Support Hours": 42.00},
  "mismatch_check": {
    "contract_expired": false,
    "price_term_mismatch": true,
    "evidence": "Contract states $42.00/unit for IT Support Hours; invoice billed at $47.60/unit"
  }
}
```

If no contract exists for the vendor:
```json
{
  "vendor_id": "V009",
  "contract_found": false,
  "mismatch_check": {"no_contract_on_file": true}
}
```

## Example CLI invocation
```
coco run contract-clause-skill --vendor_id V003 --invoice_context '{"invoiced_unit_price": 47.60, "line_item": "IT Support Hours", "invoice_date": "2026-07-10"}'
```

## Notes for implementation
- Test this against the two deliberately mismatched vendors (see `generate_contracts.py`,
  `MISMATCH_VENDORS`) and the two expired-contract vendors (V009, V010) before wiring into
  orchestration — confirm extraction is correct on all four before moving to Week 3.
- Contracts are formatted differently on purpose (formal MSA, prose-embedded pricing,
  awkward vendor template, renewal-amendment-only). If extraction only works on one format,
  that's a signal the parsing logic is too narrow — this is exactly what the judging
  criteria means by "demonstrate contextual understanding," not just keyword matching.
