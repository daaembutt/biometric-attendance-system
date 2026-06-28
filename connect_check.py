import os
import sys

# Allow running as: python biometric_system/connect_check.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DB_CONFIG, ODOO_CONFIG

import psycopg2
import xmlrpc.client


def _print_effective_configs():
    print("    Effective DB_CONFIG:")
    print(
        "      host={host} port={port} db={database} user={user}".format(**DB_CONFIG)
    )
    print("    Effective ODOO_CONFIG:")
    print(
        "      url={url} db={db} username={username}".format(
            url=ODOO_CONFIG.get("url"),
            db=ODOO_CONFIG.get("db"),
            username=ODOO_CONFIG.get("username"),
        )
    )




def check_postgres():
    print("[1/2] Checking PostgreSQL connection...")
    # Don’t print password, but do show target host/port/db/user
    print(
        "    Target:",
        f"host={DB_CONFIG.get('host')}",
        f"port={DB_CONFIG.get('port')}",
        f"db={DB_CONFIG.get('database')}",
        f"user={DB_CONFIG.get('user')}",
    )
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT 1")
    _ = cur.fetchone()
    cur.close()
    conn.close()
    print("✅ PostgreSQL connected")


def check_odoo():
    print("[2/2] Checking Odoo XML-RPC authentication...")
    common = xmlrpc.client.ServerProxy(f"{ODOO_CONFIG['url']}/xmlrpc/2/common")
    uid = common.authenticate(
        ODOO_CONFIG["db"],
        ODOO_CONFIG["username"],
        ODOO_CONFIG["password"],
        {},
    )
    if not uid:
        raise RuntimeError("Odoo authentication failed (uid is False/None)")
    print(f"✅ Odoo authenticated (uid={uid})")


def main():
    try:
        check_postgres()
        check_odoo()
        print("\n🎉 DB and Odoo connections are OK")
    except Exception as e:
        print("\n❌ Connection check failed:")
        print(e)
        raise


if __name__ == "__main__":
    main()

