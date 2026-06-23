#!/usr/bin/env python
"""Simple reconciliation between a source CSV file and an Oracle target table.

Usage example:
    python oracle_reconciliation.py \
        --source-file data.csv \
        --oracle-user APPUSER \
        --oracle-password secret \
        --oracle-dsn "host:1521/service" \
        --oracle-table TARGET_TABLE \
        --key-columns id \
        --compare-columns amount,date,status \
        --report-file reconciliation_report.csv
"""

import argparse
import csv
import importlib
import os
from collections import OrderedDict

oracledb_driver = None
for module_name in ("oracledb", "cx_Oracle"):
    try:
        oracledb_driver = importlib.import_module(module_name)
        break
    except ImportError:
        continue


def parse_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def load_source_csv(source_file, key_columns, compare_columns=None, delimiter=","):
    if not os.path.isfile(source_file):
        raise FileNotFoundError(f"Source file not found: {source_file}")

    with open(source_file, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("Source file must have a header row.")

        fieldnames = [name.strip() for name in reader.fieldnames]
        missing = [col for col in key_columns if col not in fieldnames]
        if missing:
            raise ValueError(f"Missing key columns in source file: {missing}")
        if compare_columns:
            missing = [col for col in compare_columns if col not in fieldnames]
            if missing:
                raise ValueError(f"Missing compare columns in source file: {missing}")

        source_map = OrderedDict()
        for row in reader:
            key = tuple(row[col].strip() for col in key_columns)
            if key in source_map:
                raise ValueError(f"Duplicate key found in source file: {key}")
            source_map[key] = {col: row[col].strip() for col in (compare_columns or fieldnames if compare_columns else fieldnames)}

    return source_map


def connect_oracle(user, password, dsn):
    if oracledb_driver is None:
        raise ImportError(
            "No Oracle driver installed. Install 'oracledb' or 'cx_Oracle' to proceed."
        )
    return oracledb_driver.connect(user=user, password=password, dsn=dsn)


def fetch_oracle_map(connection, table, key_columns, compare_columns=None, where_clause=None, debug=False):
    columns = key_columns + (compare_columns or [])
    select_list = ", ".join(columns)
    query = f"SELECT {select_list} FROM {table}"
    if where_clause:
        query = f"{query} WHERE {where_clause}"

    oracle_map = OrderedDict()
    cursor = connection.cursor()
    try:
        if debug:
            print(f"Executing Oracle query: {query}")
        cursor.execute(query)
        rows = cursor.fetchall()
        if debug:
            print(f"Fetched Oracle rows: {len(rows)}")
        for row in rows:
            key = tuple(normalize_value(value) for value in row[: len(key_columns)])
            values = {col: normalize_value(row[i + len(key_columns)]) for i, col in enumerate(compare_columns or [])}
            if key in oracle_map:
                raise ValueError(f"Duplicate key found in Oracle table result: {key}")
            oracle_map[key] = values
    finally:
        cursor.close()

    return oracle_map


def prepare_insert_rows(source_map, key_columns, **kwargs):
    if not source_map:
        return [], []

    sample_row = next(iter(source_map.values()))
    insert_columns = key_columns + [col for col in sample_row if col not in key_columns]
    rows = []
    for key, values in source_map.items():
        row_values = [values.get(col, "") for col in insert_columns]
        rows.append(tuple(row_values))
    return insert_columns, rows


def load_source_to_oracle(connection, table, insert_columns, rows, truncate=False, debug=False):
    cursor = connection.cursor()
    try:
        if truncate:
            delete_sql = f"DELETE FROM {table}"
            if debug:
                print(f"Truncating Oracle table with: {delete_sql}")
            cursor.execute(delete_sql)

        if not rows:
            if debug:
                print("No source rows provided for Oracle load.")
            return

        col_list = ", ".join(insert_columns)
        bind_list = ", ".join(f":{i+1}" for i in range(len(insert_columns)))
        insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({bind_list})"
        if debug:
            print(f"Loading Oracle table with SQL: {insert_sql}")
            print(f"Loading {len(rows)} rows into Oracle table {table}")
        cursor.executemany(insert_sql, rows)
        connection.commit()
    finally:
        cursor.close()


def normalize_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def compare_rows(source_map, oracle_map, key_columns, compare_columns):
    mismatches = []
    missing_in_oracle = []
    extra_in_oracle = []

    for key, source_values in source_map.items():
        target_values = oracle_map.get(key)
        if target_values is None:
            missing_in_oracle.append(key)
            continue

        row_diff = {}
        for col in compare_columns:
            source_value = source_values.get(col, "")
            target_value = target_values.get(col, "")
            if source_value != target_value:
                row_diff[col] = {
                    "source": source_value,
                    "oracle": target_value,
                }
        if row_diff:
            mismatches.append({
                "key": key,
                "differences": row_diff,
            })

    for key in oracle_map:
        if key not in source_map:
            extra_in_oracle.append(key)

    return missing_in_oracle, extra_in_oracle, mismatches


def reconcile(
    source_file,
    oracle_user,
    oracle_password,
    oracle_dsn,
    oracle_table,
    key_columns,
    compare_columns,
    report_file="reconciliation_report.csv",
    delimiter=",",
    where=None,
    load_target=False,
    truncate_target=False,
    debug=False,
):
    """Programmatic entry point for reconciliation.

    Returns a summary dict and writes the CSV report.
    """
    key_cols = key_columns if isinstance(key_columns, (list, tuple)) else parse_list(key_columns)
    compare_cols = compare_columns if isinstance(compare_columns, (list, tuple)) else parse_list(compare_columns)

    source_map = load_source_csv(source_file, key_cols, compare_columns=compare_cols, delimiter=delimiter)

    connection = connect_oracle(oracle_user, oracle_password, oracle_dsn)
    try:
        if load_target:
            insert_columns, insert_rows = prepare_insert_rows(source_map, key_cols)
            load_source_to_oracle(connection, oracle_table, insert_columns, insert_rows, truncate=truncate_target, debug=debug)

        oracle_map = fetch_oracle_map(connection, oracle_table, key_cols, compare_columns=compare_cols, where_clause=where, debug=debug)
    finally:
        try:
            connection.close()
        except Exception:
            pass

    missing, extra, mismatches = compare_rows(source_map, oracle_map, key_cols, compare_cols)
    write_report(report_file, key_cols, compare_cols, missing, extra, mismatches)

    return {
        "source_rows": len(source_map),
        "oracle_rows": len(oracle_map),
        "missing_in_oracle": len(missing),
        "extra_in_oracle": len(extra),
        "value_mismatches": len(mismatches),
        "report_file": report_file,
    }


def write_report(report_file, key_columns, compare_columns, missing, extra, mismatches):
    with open(report_file, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["reconciliation_type"] + [f"key_{i + 1}" for i in range(len(key_columns))] + ["column_name", "source_value", "oracle_value"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for key in missing:
            row = {"reconciliation_type": "MISSING_IN_ORACLE"}
            row.update({f"key_{i + 1}": key[i] for i in range(len(key_columns))})
            writer.writerow(row)

        for key in extra:
            row = {"reconciliation_type": "EXTRA_IN_ORACLE"}
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
                    "oracle_value": diff["oracle"],
                }
                writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Reconcile a source CSV file against an Oracle table.")
    parser.add_argument("--source-file", required=True, help="Path to the source CSV file.")
    parser.add_argument("--oracle-user", required=True, help="Oracle database username.")
    parser.add_argument("--oracle-password", required=True, help="Oracle database password.")
    parser.add_argument("--oracle-dsn", required=True, help="Oracle DSN string, for example host:port/service_name.")
    parser.add_argument("--oracle-table", required=True, help="Oracle table name to compare against.")
    parser.add_argument("--key-columns", required=True, help="Comma-separated key columns shared between source file and Oracle table.")
    parser.add_argument("--compare-columns", required=True, help="Comma-separated columns to compare.")
    parser.add_argument("--report-file", default="D:\\SYAM\\Courses\\Practice_files\\reconciliation_report.csv", help="Output CSV report file path.")
    parser.add_argument("--delimiter", default=",", help="Delimiter for the source CSV file. Default is comma.")
    parser.add_argument("--where", help="Optional Oracle WHERE clause to filter target table rows.")
    parser.add_argument("--load-target", action="store_true", help="Load source CSV rows into the Oracle target table before reconciliation.")
    parser.add_argument("--truncate-target", action="store_true", help="Delete existing rows from the Oracle target table before loading source rows.")
    parser.add_argument("--debug", action="store_true", help="Enable debug output for the Oracle query and row counts.")

    args = parser.parse_args()
    key_columns = parse_list(args.key_columns)
    compare_columns = parse_list(args.compare_columns)

    source_map = load_source_csv(
        args.source_file,
        key_columns,
        compare_columns=compare_columns,
        delimiter=args.delimiter,
    )

    connection = connect_oracle(args.oracle_user, args.oracle_password, args.oracle_dsn)
    if args.load_target:
        insert_columns, insert_rows = prepare_insert_rows(source_map, key_columns)
        load_source_to_oracle(
            connection,
            args.oracle_table,
            insert_columns,
            insert_rows,
            truncate=args.truncate_target,
            debug=args.debug,
        )

    oracle_map = fetch_oracle_map(
        connection,
        args.oracle_table,
        key_columns,
        compare_columns=compare_columns,
        where_clause=args.where,
        debug=args.debug,
    )
    connection.close()

    missing, extra, mismatches = compare_rows(source_map, oracle_map, key_columns, compare_columns)
    write_report(args.report_file, key_columns, compare_columns, missing, extra, mismatches)

    print("Reconciliation complete.")
    print(f"Source rows: {len(source_map)}")
    print(f"Oracle rows: {len(oracle_map)}")
    print(f"Missing in Oracle: {len(missing)}")
    print(f"Extra in Oracle: {len(extra)}")
    print(f"Value mismatches: {len(mismatches)}")
    print(f"Report written to: {args.report_file}")


if __name__ == "__main__":
    main()
