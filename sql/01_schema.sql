-- AP Autopilot: core schema
-- Run this first, in your AP_AUTOPILOT_WH warehouse / a fresh database.

CREATE DATABASE IF NOT EXISTS AP_AUTOPILOT;
CREATE SCHEMA IF NOT EXISTS AP_AUTOPILOT.CORE;
USE SCHEMA AP_AUTOPILOT.CORE;

-- Vendor master
CREATE OR REPLACE TABLE VENDORS (
    vendor_id         VARCHAR(20) PRIMARY KEY,
    vendor_name       VARCHAR(200),
    contract_id       VARCHAR(20),
    contract_start    DATE,
    contract_end      DATE,           -- NULL or past date = expired
    contracted_terms  VARCHAR(50),    -- e.g. 'NET_30'
    contact_email     VARCHAR(200)
);

-- Purchase orders
CREATE OR REPLACE TABLE PURCHASE_ORDERS (
    po_id             VARCHAR(20) PRIMARY KEY,
    vendor_id         VARCHAR(20) REFERENCES VENDORS(vendor_id),
    line_item         VARCHAR(200),
    unit_price        NUMBER(12,2),
    quantity          NUMBER(10,0),
    po_date           DATE
);

-- Invoices (the thing being reconciled)
CREATE OR REPLACE TABLE INVOICES (
    invoice_id        VARCHAR(20) PRIMARY KEY,
    vendor_id         VARCHAR(20) REFERENCES VENDORS(vendor_id),
    po_id             VARCHAR(20) REFERENCES PURCHASE_ORDERS(po_id),
    line_item         VARCHAR(200),
    invoiced_unit_price NUMBER(12,2),
    invoiced_quantity NUMBER(10,0),
    invoice_amount    NUMBER(14,2),
    invoice_date      DATE,
    payment_terms_stated VARCHAR(50)
);

-- Payment history (for duplicate detection + timing checks)
CREATE OR REPLACE TABLE PAYMENT_HISTORY (
    payment_id        VARCHAR(20) PRIMARY KEY,
    invoice_id        VARCHAR(20) REFERENCES INVOICES(invoice_id),
    amount_paid       NUMBER(14,2),
    payment_date      DATE
);

-- Audit log — every AP Autopilot decision lands here
CREATE OR REPLACE TABLE AUDIT_LOG (
    log_id            VARCHAR(36) DEFAULT UUID_STRING(),
    invoice_id        VARCHAR(20),
    vendor_id         VARCHAR(20),
    decision          VARCHAR(20),    -- 'APPROVE' | 'HOLD' | 'ESCALATE'
    anomaly_evidence  VARIANT,        -- raw output of invoice-anomaly-skill
    contract_evidence VARIANT,        -- raw output of contract-clause-skill
    reasoning         VARCHAR(2000),  -- human-readable explanation
    decided_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Stage for contract PDFs (used in 03_stage_and_search.sql)
CREATE OR REPLACE STAGE CONTRACT_DOCS
    DIRECTORY = (ENABLE = TRUE)
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');
