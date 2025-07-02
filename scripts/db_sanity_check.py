import csv
import os
from app.config import Config
from app.services.csv_db import CSVDatabase
from app.models.guest import Guest


def run_sanity_check():
    config = Config()
    csv_path = config.get('DATABASE', 'CSVPath')
    backup_dir = config.get('DATABASE', 'BackupDir')
    db = CSVDatabase(csv_path, backup_dir)

    # Determine required headers and defaults from Guest model
    default_guest = Guest()
    required_fields = list(default_guest.to_dict().keys())
    default_values = default_guest.to_dict()

    data = db.read_all()
    updated = False
    cleaned_rows = []
    seen_ids = set()

    for row in data:
        # Remove unknown columns
        row = {k: v for k, v in row.items() if k in required_fields}

        # Add missing columns with defaults
        for field in required_fields:
            if field not in row or row[field] is None:
                row[field] = default_values[field]
                updated = True

        # Ensure ID uniqueness (skip empty or duplicate)
        gid = row.get('ID')
        if not gid or gid in seen_ids:
            # Generate a new ID if missing or duplicate
            row['ID'] = Guest().id
            updated = True
        seen_ids.add(row['ID'])

        cleaned_rows.append(row)

    if updated:
        db.write_all(cleaned_rows, fieldnames=required_fields)
        print(f"Database sanitized. {len(cleaned_rows)} records updated.")
    else:
        print("Database is already consistent. No changes made.")


if __name__ == '__main__':
    run_sanity_check()
