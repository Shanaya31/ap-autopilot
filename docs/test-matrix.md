# AP Autopilot Test Matrix

| Test case | Input | Expected decision | Expected source | Expected behavior | Status |
|---|---|---|---|---|---|
| Expired contract | `INV0007` | `ESCALATE` | `PYTHON_FAIL_SAFE` | Invoice is escalated because vendor V002 has an expired contract | Passed |
| Active contract with price mismatch | `INV0013` | `MANUAL REVIEW` | `SNOWFLAKE_SQL` | Detects the 12% contract-versus-PO price mismatch for V003 | Passed |
| Clean active contract | `INV0018` | `AUTO APPROVE` | `SNOWFLAKE_SQL` | Approves an invoice with an active contract and no pricing anomaly | Passed |
| Missing contract analysis | Add or test a vendor with no contract record | `ESCALATE` | `PYTHON_FAIL_SAFE` | Missing contract evidence must never silently pass | Pending |
| Invalid invoice ID | `INV9999` | Input error | N/A | CLI prints a friendly error and does not write an audit row | Pending |
| Gemini unavailable | Any valid invoice during quota or availability failure | Existing SQL/Python decision remains unchanged | Existing source | CLI uses fallback memo and still writes audit row | Passed |