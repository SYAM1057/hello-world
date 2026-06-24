#!/usr/bin/env python
"""Reconcile a source CSV file against a SQLite target table."""

import argparse
import csv
import os
import sqlite3
from collections import OrderedDict


def parse_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def load_source_csv(source_file, key_columns, compare_columns=None, delimiter=","):
    if not os.path.isfile(source_file):
        raise FileNotFoundError(f"Source file not found: {source_file}")

    with open(source_file, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("Source file must have a header row.")

        fieldnames = [name.strip() for name in reader.fieldnames]
        missing_keys = [col for col in key_columns if col not in fieldnames]
        if missing_keys:
            raise ValueError(f"Missing key columns in source file: {missing_keys}")

        if compare_columns:
            missing_compare = [col for col in compare_columns if col not in fieldnames]
            if missing_compare:
                raise ValueError(f"Missing compare columns in source file: {missing_compare}")

        source_map = OrderedDict()
        for row in reader:
            key = tuple(row[col].strip() for col in key_columns)
            if key in source_map:
                raise ValueError(f"Duplicate key found in source file: {key}")
            values = {col: row[col].strip() for col in (compare_columns or fieldnames)}
            source_map[key] = values

    return source_map


def connect_sqlite(sqlite_db):
    if not os.path.isfile(sqlite_db):
        raise FileNotFoundError(f"SQLite database file not found: {sqlite_db}")
    return sqlite3.connect(sqlite_db)


def get_table_columns(connection, table_name):
    cursor = connection.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        if not columns:
            raise ValueError(f"SQLite table not found or has no columns: {table_name}")
        return columns
    finally:
        cursor.close()


def fetch_sqlite_map(connection, table_name, key_columns, compare_columns=None, where_clause=None, debug=False):
    table_columns = get_table_columns(connection, table_name)
    if compare_columns is None:
        compare_columns = [col for col in table_columns if col not in key_columns]

    missing_keys = [col for col in key_columns if col not in table_columns]
    if missing_keys:
        raise ValueError(f"Missing key columns in SQLite table: {missing_keys}")

    missing_compare = [col for col in compare_columns if col not in table_columns]
    if missing_compare:
        raise ValueError(f"Missing compare columns in SQLite table: {missing_compare}")

    select_columns = key_columns + compare_columns
    select_list = ", ".join(select_columns)
    query = f"SELECT {select_list} FROM {table_name}"
    if where_clause:
        query += f" WHERE {where_clause}"

    if debug:
        print(f"Executing SQLite query: {query}")
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        if debug:
            print(f"Fetched SQLite rows: {len(rows)}")

        sqlite_map = OrderedDict()
        for row in rows:
            key = tuple(normalize_value(value) for value in row[: len(key_columns)])
            values = {
                col: normalize_value(row[i + len(key_columns)])
                for i, col in enumerate(compare_columns)
            }
            if key in sqlite_map:
                raise ValueError(f"Duplicate key found in SQLite table result: {key}")
            sqlite_map[key] = values
        return sqlite_map
    finally:
        cursor.close()


def normalize_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def compare_rows(source_map, target_map, key_columns, compare_columns):
    missing_in_target = []
    extra_in_target = []
    mismatches = []

    for key, source_values in source_map.items():
        target_values = target_map.get(key)
        if target_values is None:
            missing_in_target.append(key)
            continue

        row_diff = {}
        for col in compare_columns:
            source_value = source_values.get(col, "")
            target_value = target_values.get(col, "")
            if source_value != target_value:
                row_diff[col] = {"source": source_value, "target": target_value}

        if row_diff:
            mismatches.append({"key": key, "differences": row_diff})

    for key in target_map:
        if key not in source_map:
            extra_in_target.append(key)

    return missing_in_target, extra_in_target, mismatches


def write_report(report_file, key_columns, compare_columns, missing, extra, mismatches):
    with open(report_file, mode="w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["reconciliation_type"] + [f"key_{i + 1}" for i in range(len(key_columns))] + ["column_name", "source_value", "target_value"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for key in missing:
            row = {"reconciliation_type": "MISSING_IN_TARGET"}
            row.update({f"key_{i + 1}": key[i] for i in range(len(key_columns))})
            writer.writerow(row)

        for key in extra:
            row = {"reconciliation_type": "EXTRA_IN_TARGET"}
            row.update({f"key_{i + 1}": key[i] for i in range(len(key_columns))})
            writer.writerow(row)

        for item in mismatches:
            key = item["key"]
            for col, diff in item["differences"].items():
                row = {
                    "reconciliation_type": "VALUE_MISMATCH",
                    **{f"key_{i + 1}": key[i] for i in range(len(key_columns))},
                    "column_name": col,
                    "source_value": diff["source"],
                    "target_value": diff["target"],
                }
                writer.writerow(row)


def reconcile(
    source_file,
    sqlite_db,
    table_name,
    key_columns,
    compare_columns,
    report_file="reconciliation_report.csv",
    delimiter=",",
    where=None,
    debug=False,
):
    key_cols = key_columns if isinstance(key_columns, (list, tuple)) else parse_list(key_columns)
    compare_cols = compare_columns if isinstance(compare_columns, (list, tuple)) else (parse_list(compare_columns) if compare_columns else None)

    source_map = load_source_csv(source_file, key_cols, compare_columns=compare_cols, delimiter=delimiter)
    connection = connect_sqlite(sqlite_db)
    try:
        target_map = fetch_sqlite_map(connection, table_name, key_cols, compare_columns=compare_cols, where_clause=where, debug=debug)
    finally:
        connection.close()

    if compare_cols is None:
        if source_map:
            sample_row = next(iter(source_map.values()))
            compare_cols = [col for col in sample_row if col not in key_cols]
        else:
            compare_cols = []

    missing, extra, mismatches = compare_rows(source_map, target_map, key_cols, compare_cols)
    write_report(report_file, key_cols, compare_cols, missing, extra, mismatches)

    return {
        "source_rows": len(source_map),
        "target_rows": len(target_map),
        "missing_in_target": len(missing),
        "extra_in_target": len(extra),
        "value_mismatches": len(mismatches),
        "report_file": report_file,
    }


def main():
    parser = argparse.ArgumentParser(description="Reconcile a source CSV file against a SQLite table.")
    parser.add_argument("--source-file", required=True, help="Path to the source CSV file.")
    parser.add_argument("--sqlite-db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--table", required=True, help="SQLite target table name.")
    parser.add_argument("--key-columns", required=True, help="Comma-separated key columns shared between source file and target table.")
    parser.add_argument("--compare-columns", help="Comma-separated columns to compare. If omitted, compares all non-key source columns.")
    parser.add_argument("--report-file", default="reconciliation_report.csv", help="Output CSV report file path.")
    parser.add_argument("--delimiter", default=",", help="Delimiter for the source CSV file. Default is comma.")
    parser.add_argument("--where", help="Optional SQLite WHERE clause to filter target table rows.")
    parser.add_argument("--debug", action="store_true", help="Enable debug output for the SQLite query and row counts.")

    args = parser.parse_args()
    result = reconcile(
        source_file=args.source_file,
        sqlite_db=args.sqlite_db,
        table_name=args.table,
        key_columns=parse_list(args.key_columns),
        compare_columns=parse_list(args.compare_columns) if args.compare_columns else None,
        report_file=args.report_file,
        delimiter=args.delimiter,
        where=args.where,
        debug=args.debug,
    )

    print("Reconciliation complete.")
    print(f"Source rows: {result['source_rows']}")
    print(f"Target rows: {result['target_rows']}")
    print(f"Missing in target: {result['missing_in_target']}")
    print(f"Extra in target: {result['extra_in_target']}")
    print(f"Value mismatches: {result['value_mismatches']}")
    print(f"Report written to: {result['report_file']}")


if __name__ == "__main__":
    main()
