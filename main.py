# ============================================================
# SMART BIOMETRIC ATTENDANCE SYSTEM (PKT FIXED VERSION)
# ============================================================

import os
import sys

# ─────────────────────────────────────────────
# Path fix for running script
# ─────────────────────────────────────────────
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────
try:
    from .register_face import register_face
    from .attendance import run_attendance, print_today_report
    from .odoo_sync import sync_attendance_to_odoo

except ImportError:
    from register_face import register_face
    from attendance import run_attendance, print_today_report
    from odoo_sync import sync_attendance_to_odoo



# ─────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────
def main_menu():
    while True:
        print("\n" + "=" * 39)
        print("   SMART BIOMETRIC ATTENDANCE SYSTEM   ")
        print("=" * 39)
        print("1. Register Employee Face")
        print("2. Start Check-In")
        print("3. Start Check-Out")
        print("4. View Today's Report")
        print("5. Sync to Odoo")
        print("6. Exit")

        try:
            choice = input("Select option (1-6): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Exiting...")
            break


        if choice == "1":
            try:
                emp_id = int(input("Enter Employee ID: ").strip())
                ok = register_face(emp_id)

                if ok:
                    print("✅ Registration complete")
                else:
                    print("❌ Registration failed/cancelled")

            except ValueError:
                print("❌ Invalid Employee ID")

        elif choice == "2":
            print("🟢 Check-In recorded (Pakistan Time)")
            run_attendance("check_in")

        elif choice == "3":
            print("🔴 Check-Out recorded (Pakistan Time)")
            run_attendance("check_out")

        elif choice == "4":
            print("\n📊 TODAY'S ATTENDANCE REPORT (PKT)")
            print("=" * 50)

            # IMPORTANT: This assumes your report returns records
            print_today_report()

        elif choice == "5":
            print("🔄 Syncing to Odoo...")
            sync_attendance_to_odoo()

        elif choice == "6":
            print("👋 Exiting...")
            break

        else:
            print("❌ Invalid option. Please select 1-6.")


# ─────────────────────────────────────────────
# RUN PROGRAM
# ─────────────────────────────────────────────
if __name__ == "__main__":
    main_menu()