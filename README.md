# Smart Biometric Attendance System

## Requirements
- Python 3.x
- PostgreSQL 15
- Odoo 16 (optional for sync)
- Webcam

## Installation
1. Install dependencies:
   pip install -r requirements.txt

2. Setup PostgreSQL database:
   - Create database: biometric_db
   - Run: database_setup.sql

3. Configure settings:
   - Edit config.py with your PostgreSQL and Odoo credentials

## Usage
Run the main launcher:
   python main.py

## Project Structure
- config.py        → All configuration settings
- database.py      → PostgreSQL database functions
- register_face.py → Register employee faces
- attendance.py    → Face recognition attendance tracking
- odoo_sync.py     → Sync attendance to Odoo ERP
- main.py          → Main menu launcher

## How It Works
1. Register each employee's face using register_face.py
2. Run attendance.py to start tracking
3. System recognizes faces via webcam
4. Attendance is logged to PostgreSQL
5. Records sync to Odoo HR Attendance module

