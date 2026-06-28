import os
import sys
import xmlrpc.client

# Allow running as: python biometric_system/odoo_inspect.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from .config import ODOO_CONFIG
except ImportError:
    from config import ODOO_CONFIG


def main():

    common = xmlrpc.client.ServerProxy(f"{ODOO_CONFIG['url']}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['username'], ODOO_CONFIG['password'], {})
    if not uid:
        raise SystemExit('Authentication failed')

    models = xmlrpc.client.ServerProxy(f"{ODOO_CONFIG['url']}/xmlrpc/2/object")

    barcode = '3764'
    emp_ids = models.execute_kw(
        ODOO_CONFIG['db'], uid, ODOO_CONFIG['password'],
        'hr.employee', 'search', [[('barcode', '=', barcode)]],
        {'limit': 5},
    )
    print('emp_ids', emp_ids)
    if not emp_ids:
        return

    employee_id = emp_ids[0]

    # open attendance (no check_out)
    open_ids = models.execute_kw(
        ODOO_CONFIG['db'], uid, ODOO_CONFIG['password'],
        'hr.attendance', 'search',
        [[('employee_id', '=', employee_id), ('check_out', '=', False)]],
        {'limit': 5},
    )
    print('open_ids', open_ids)

    if open_ids:
        open_recs = models.execute_kw(
            ODOO_CONFIG['db'], uid, ODOO_CONFIG['password'],
            'hr.attendance', 'read',
            [open_ids],
            {'fields': ['id', 'check_in', 'check_out', 'employee_id']},
        )
        print('open_recs', open_recs)


if __name__ == '__main__':
    main()

