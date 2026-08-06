-- Contract document ingestion + Cortex Search service.
-- Upload your synthetic contract PDFs to the CONTRACT_DOCS stage first:
--   snowsql> PUT file:///local/path/contracts/*.pdf @CONTRACT_DOCS AUTO_COMPRESS=FALSE;
-- or drag-and-drop via Snowsight's stage UI.

USE SCHEMA AP_AUTOPILOT.CORE;

-- 1. Parse PDFs into raw text using Cortex's document AI function.
--    (Function name/signature may vary by release -- check
--    docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview
--    and the AISQL docs for the current PARSE_DOCUMENT / AI_PARSE syntax.)
CREATE OR REPLACE TABLE CONTRACT_TEXT AS
SELECT
    RELATIVE_PATH AS file_name,
    SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
        '@CONTRACT_DOCS', RELATIVE_PATH, {'mode': 'LAYOUT'}
    ):content::STRING AS raw_text
FROM DIRECTORY(@CONTRACT_DOCS);

-- 2. Map each parsed contract to a vendor_id (do this by filename
--    convention, e.g. contract_V001.pdf -> vendor_id V001, or via a
--    small manual lookup table for your synthetic set).
CREATE OR REPLACE TABLE CONTRACT_TEXT_MAPPED AS
SELECT
    ct.file_name,
    -- adjust this extraction to match your actual filename convention
    REGEXP_SUBSTR(ct.file_name, 'V[0-9]+') AS vendor_id,
    ct.raw_text
FROM CONTRACT_TEXT ct;

-- 3. Create the Cortex Search service over parsed contract text.
CREATE OR REPLACE CORTEX SEARCH SERVICE CONTRACT_SEARCH_SVC
    ON raw_text
    ATTRIBUTES vendor_id, file_name
    WAREHOUSE = AP_AUTOPILOT_WH
    TARGET_LAG = '1 hour'
    AS (
        SELECT vendor_id, file_name, raw_text
        FROM CONTRACT_TEXT_MAPPED
    );

-- 4. Test query (run manually):
-- SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
--     'CONTRACT_SEARCH_SVC',
--     '{"query": "unit price and renewal terms for vendor V003", "limit": 1}'
-- );
