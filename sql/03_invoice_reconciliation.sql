USE ROLE ACCOUNTADMIN;
USE WAREHOUSE AP_AUTOPILOT_WH;
USE DATABASE AP_AUTOPILOT;
USE SCHEMA CORE;

CREATE OR REPLACE VIEW INVOICE_RECONCILIATION AS
SELECT
    i.invoice_id,
    i.vendor_id,
    i.po_id,
    i.line_item,
    i.invoiced_unit_price,
    i.invoiced_quantity,
    i.invoice_amount,
    i.invoice_date,
    i.payment_terms_stated,

    p.unit_price AS po_unit_price,
    p.quantity AS po_quantity,
    p.po_date,

    i.invoiced_unit_price - p.unit_price AS price_delta,

    ROUND(
        (
            i.invoiced_unit_price - p.unit_price
        )
        / NULLIF(p.unit_price, 0)
        * 100,
        2
    ) AS price_delta_pct,

    i.invoiced_quantity - p.quantity AS quantity_delta,

    v.vendor_name,
    v.contract_id,
    v.contract_start,
    v.contract_end,
    v.contracted_terms,
    v.contact_email

FROM INVOICES i

LEFT JOIN PURCHASE_ORDERS p
    ON i.po_id = p.po_id

LEFT JOIN VENDORS v
    ON i.vendor_id = v.vendor_id;