"""
Shared Snowflake connection for all CLI skills.

Environment variables required (.env):

SNOWFLAKE_ACCOUNT
SNOWFLAKE_USER
SNOWFLAKE_PASSWORD
SNOWFLAKE_WAREHOUSE
SNOWFLAKE_DATABASE
SNOWFLAKE_SCHEMA
SNOWFLAKE_ROLE
"""

import os

from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector import DictCursor

# Load variables from .env
load_dotenv()


def get_connection():
    """Create and return a Snowflake connection."""
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "AP_AUTOPILOT_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "AP_AUTOPILOT"),
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "CORE"),
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    )


def query(sql, params=None):
    """
    Execute a SELECT query and return rows as a list of dictionaries.
    """
    conn = get_connection()
    cur = conn.cursor(DictCursor)

    try:
        cur.execute(sql, params or {})
        return cur.fetchall()

    finally:
        cur.close()
        conn.close()


def execute(sql, params=None):
    """
    Execute an INSERT, UPDATE, DELETE, or DDL statement.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(sql, params or {})
        conn.commit()

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    try:
        rows = query("SELECT COUNT(*) AS N FROM VENDORS")
        print(f"✅ Connected successfully!")
        print(f"VENDORS table contains {rows[0]['N']} rows.")

    except Exception as e:
        print("❌ Snowflake connection failed.")
        print(e)