USE ROLE ACCOUNTADMIN;
USE WAREHOUSE AP_AUTOPILOT_WH;
USE DATABASE AP_AUTOPILOT;
USE SCHEMA CORE;

CREATE OR REPLACE SEMANTIC VIEW AP_SEMANTIC_VIEW

    TABLES (
        reconciliation AS AP_AUTOPILOT.CORE.INVOICE_RECONCILIATION
            PRIMARY KEY (invoice_id),

        payment_history AS AP_AUTOPILOT.CORE.PAYMENT_HISTORY
            PRIMARY KEY (payment_id)
    )

    RELATIONSHIPS (
        payment_to_reconciliation AS
            payment_history (invoice_id)
            REFERENCES reconciliation (invoice_id)
    )

    FACTS (
        reconciliation.invoiced_unit_price_fact
            AS invoiced_unit_price,

        reconciliation.po_unit_price_fact
            AS po_unit_price,

        reconciliation.invoiced_quantity_fact
            AS invoiced_quantity,

        reconciliation.po_quantity_fact
            AS po_quantity,

        reconciliation.invoice_amount_fact
            AS invoice_amount,

        reconciliation.price_delta
            AS price_delta,

        reconciliation.price_delta_pct
            AS price_delta_pct,

        reconciliation.quantity_delta
            AS quantity_delta,

        payment_history.amount_paid_fact
            AS amount_paid
    )

    DIMENSIONS (
        reconciliation.invoice_id
            AS invoice_id,

        reconciliation.vendor_id
            AS vendor_id,

        reconciliation.vendor_name
            AS vendor_name,

        reconciliation.po_id
            AS po_id,

        reconciliation.invoice_line_item
            AS line_item,

        reconciliation.invoice_date
            AS invoice_date,

        reconciliation.po_date
            AS po_date,

        reconciliation.payment_terms_stated
            AS payment_terms_stated,

        reconciliation.contract_id
            AS contract_id,

        reconciliation.contract_start
            AS contract_start,

        reconciliation.contract_end
            AS contract_end,

        reconciliation.contracted_terms
            AS contracted_terms,

        payment_history.payment_id
            AS payment_id,

        payment_history.payment_date
            AS payment_date
    )

    METRICS (
        reconciliation.total_invoice_amount
            AS SUM(invoice_amount),

        reconciliation.invoice_count
            AS COUNT(invoice_id),

        reconciliation.average_invoice_amount
            AS AVG(invoice_amount),

        reconciliation.average_price_delta_pct
            AS AVG(price_delta_pct),

        reconciliation.total_price_overcharge
            AS SUM(
                CASE
                    WHEN price_delta > 0
                    THEN price_delta * invoiced_quantity
                    ELSE 0
                END
            ),

        payment_history.total_amount_paid
            AS SUM(amount_paid)
    )

    COMMENT =
        'Semantic view for AP invoice reconciliation, contract compliance, purchase-order matching, and payment analysis';