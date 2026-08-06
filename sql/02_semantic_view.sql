-- Cortex Analyst semantic view over the structured tables.
-- This is what lets invoice-anomaly-skill (and you, ad hoc) ask
-- plain-English questions and get correct SQL back.
--
-- NOTE: exact semantic-view DDL syntax evolves with Snowflake Cortex
-- releases -- check current docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst
-- for the latest CREATE SEMANTIC VIEW syntax before running. Structure below
-- reflects the relationships/measures you need regardless of exact syntax version.

USE SCHEMA AP_AUTOPILOT.CORE;

CREATE OR REPLACE SEMANTIC VIEW AP_SEMANTIC_VIEW
    TABLES (
        invoices AS INVOICES
            PRIMARY KEY (invoice_id),
        purchase_orders AS PURCHASE_ORDERS
            PRIMARY KEY (po_id),
        vendors AS VENDORS
            PRIMARY KEY (vendor_id),
        payment_history AS PAYMENT_HISTORY
            PRIMARY KEY (payment_id)
    )
    RELATIONSHIPS (
        invoices_to_po AS invoices (po_id) REFERENCES purchase_orders (po_id),
        invoices_to_vendor AS invoices (vendor_id) REFERENCES vendors (vendor_id),
        payment_to_invoice AS payment_history (invoice_id) REFERENCES invoices (invoice_id)
    )
    FACTS (
        invoices.price_delta AS invoices.invoiced_unit_price - purchase_orders.unit_price,
        invoices.price_delta_pct AS
            (invoices.invoiced_unit_price - purchase_orders.unit_price) / NULLIF(purchase_orders.unit_price, 0) * 100
    )
    DIMENSIONS (
        vendors.vendor_name,
        vendors.contract_end,
        invoices.invoice_date,
        invoices.line_item
    )
    METRICS (
        invoices.total_invoice_amount AS SUM(invoices.invoice_amount),
        invoices.invoice_count AS COUNT(invoices.invoice_id)
    );

-- Sanity-check queries to run manually before wiring up the skill:

-- 1. Which invoices are priced above their PO?
-- SELECT invoice_id, vendor_id, price_delta_pct FROM AP_SEMANTIC_VIEW
-- WHERE price_delta_pct > 5 ORDER BY price_delta_pct DESC;

-- 2. Which vendors have an expired contract but recent invoices?
-- SELECT DISTINCT v.vendor_name, v.contract_end, i.invoice_date
-- FROM INVOICES i JOIN VENDORS v ON i.vendor_id = v.vendor_id
-- WHERE v.contract_end < i.invoice_date;

-- 3. Duplicate invoice candidates (same vendor + amount within 3 days)
-- SELECT a.invoice_id, b.invoice_id, a.vendor_id, a.invoice_amount
-- FROM INVOICES a JOIN INVOICES b
--   ON a.vendor_id = b.vendor_id AND a.invoice_amount = b.invoice_amount
--   AND a.invoice_id < b.invoice_id
--   AND ABS(DATEDIFF('day', a.invoice_date, b.invoice_date)) <= 3;
