CREATE OR REPLACE TABLE CONTRACT_CLAUSE_FLAGS AS
SELECT
    FILE_NAME,
    VENDOR_ID,

    IFF(
        SEARCHABLE_TEXT LIKE '%automatic renew%'
        OR SEARCHABLE_TEXT LIKE '%automatically renew%',
        TRUE,
        FALSE
    ) AS HAS_AUTOMATIC_RENEWAL,

    IFF(
        SEARCHABLE_TEXT LIKE '%explicit renegotiation%'
        OR SEARCHABLE_TEXT LIKE '%renegotiat%',
        TRUE,
        FALSE
    ) AS REQUIRES_RENEGOTIATION,

    IFF(
        SEARCHABLE_TEXT LIKE '%late payment%'
        OR SEARCHABLE_TEXT LIKE '%overdue balance%'
        OR SEARCHABLE_TEXT LIKE '%1.5 percent%'
        OR SEARCHABLE_TEXT LIKE '%1.5%',
        TRUE,
        FALSE
    ) AS HAS_LATE_PAYMENT_PENALTY,

    IFF(
        SEARCHABLE_TEXT LIKE '%price increase%'
        OR SEARCHABLE_TEXT LIKE '%advance written notice%'
        OR SEARCHABLE_TEXT LIKE '%30 days notice%'
        OR SEARCHABLE_TEXT LIKE '%30 days'' notice%',
        TRUE,
        FALSE
    ) AS HAS_PRICE_INCREASE_NOTICE,

    IFF(
        SEARCHABLE_TEXT LIKE '%termination%'
        OR SEARCHABLE_TEXT LIKE '%terminate%',
        TRUE,
        FALSE
    ) AS HAS_TERMINATION_CLAUSE,

    IFF(
        SEARCHABLE_TEXT LIKE '%dispute%'
        OR SEARCHABLE_TEXT LIKE '%arbitration%',
        TRUE,
        FALSE
    ) AS HAS_DISPUTE_CLAUSE,

    CURRENT_TIMESTAMP() AS ANALYSED_AT

FROM AP_AUTOPILOT.CORE.CONTRACT_SEARCH_VIEW;