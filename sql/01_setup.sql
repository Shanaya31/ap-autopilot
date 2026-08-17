-- Setup script for AP Autopilot core schema, tables, and contract stage
-- Run this after creating AP_AUTOPILOT_WH.

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE AP_AUTOPILOT_WH;

CREATE DATABASE IF NOT EXISTS AP_AUTOPILOT;
CREATE SCHEMA IF NOT EXISTS AP_AUTOPILOT.CORE;

USE DATABASE AP_AUTOPILOT;
USE SCHEMA CORE;

-- Vendor master
CREATE OR REPLACE TABLE VENDORS (
    vendor_id         VARCHAR(20) PRIMARY KEY,
    vendor_name       VARCHAR(200),
    contract_id       VARCHAR(20),
    contract_start    DATE,
    contract_end      DATE,
    contracted_terms  VARCHAR(50),
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

-- Invoices
CREATE OR REPLACE TABLE INVOICES (
    invoice_id             VARCHAR(20) PRIMARY KEY,
    vendor_id              VARCHAR(20) REFERENCES VENDORS(vendor_id),
    po_id                  VARCHAR(20) REFERENCES PURCHASE_ORDERS(po_id),
    line_item              VARCHAR(200),
    invoiced_unit_price    NUMBER(12,2),
    invoiced_quantity      NUMBER(10,0),
    invoice_amount         NUMBER(14,2),
    invoice_date           DATE,
    payment_terms_stated   VARCHAR(50)
);

-- Payment history
CREATE OR REPLACE TABLE PAYMENT_HISTORY (
    payment_id        VARCHAR(20) PRIMARY KEY,
    invoice_id        VARCHAR(20) REFERENCES INVOICES(invoice_id),
    amount_paid       NUMBER(14,2),
    payment_date      DATE
);

-- Audit log
CREATE OR REPLACE TABLE AUDIT_LOG (
    log_id            VARCHAR(36) DEFAULT UUID_STRING(),
    invoice_id        VARCHAR(20),
    vendor_id         VARCHAR(20),
    decision          VARCHAR(20),
    anomaly_evidence  VARIANT,
    contract_evidence VARIANT,
    reasoning         VARCHAR(2000),
    decided_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Stage for contract PDFs
CREATE OR REPLACE STAGE CONTRACT_DOCS
    DIRECTORY = (ENABLE = TRUE)
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

-- Verification
SHOW TABLES IN SCHEMA AP_AUTOPILOT.CORE;
SHOW STAGES IN SCHEMA AP_AUTOPILOT.CORE;