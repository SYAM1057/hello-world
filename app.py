import os
from pathlib import Path

import gradio as gr

from sqlite_reconciliation import reconcile, parse_list


def load_uploaded_file(file_input):
    if file_input is None:
        return None
    if isinstance(file_input, dict) and "name" in file_input and "data" in file_input:
        return file_input["name"]
    if hasattr(file_input, "name"):
        return file_input.name
    return str(file_input)


def run_reconciliation(csv_file, sqlite_file, table_name, key_columns, compare_columns, delimiter=","):
    source_path = load_uploaded_file(csv_file)
    sqlite_path = load_uploaded_file(sqlite_file)

    if not source_path or not sqlite_path:
        return "Please upload both a CSV file and a SQLite database file.", ""

    try:
        result = reconcile(
            source_file=source_path,
            sqlite_db=sqlite_path,
            table_name=table_name,
            key_columns=parse_list(key_columns),
            compare_columns=parse_list(compare_columns) if compare_columns else None,
            report_file="reconciliation_report.csv",
            delimiter=delimiter,
            debug=False,
        )
    except Exception as exc:
        return f"Error: {exc}", ""

    summary = (
        f"Reconciliation complete.\n"
        f"Source rows: {result['source_rows']}\n"
        f"Target rows: {result['target_rows']}\n"
        f"Missing in target: {result['missing_in_target']}\n"
        f"Extra in target: {result['extra_in_target']}\n"
        f"Value mismatches: {result['value_mismatches']}\n"
        f"Report written to: {os.path.abspath(result['report_file'])}"
    )
    return summary, Path(result["report_file"]).read_text(encoding="utf-8")


title = "CSV to SQLite Reconciliation"

description = (
    "Upload a source CSV file and a SQLite database file, then compare a target table. "
    "The app reports missing rows, extra rows, and value mismatches, and writes a reconciliation report."
)

with gr.Blocks(title=title) as demo:
    gr.Markdown(f"# {title}")
    gr.Markdown(description)

    with gr.Row():
        csv_input = gr.File(label="Source CSV file", file_count="single", type="file")
        sqlite_input = gr.File(label="SQLite database file", file_count="single", type="file")

    table_name = gr.Textbox(label="SQLite table name", value="target_table", placeholder="Enter table name")
    key_columns = gr.Textbox(label="Key columns", value="id", placeholder="id,customer_id")
    compare_columns = gr.Textbox(label="Compare columns", value="", placeholder="Leave blank to compare all non-key columns")
    delimiter = gr.Textbox(label="CSV delimiter", value=",")

    run_button = gr.Button("Run reconciliation")
    output_text = gr.Textbox(label="Summary", lines=8)
    report_text = gr.Textbox(label="Report CSV contents", lines=16)

    run_button.click(
        run_reconciliation,
        inputs=[csv_input, sqlite_input, table_name, key_columns, compare_columns, delimiter],
        outputs=[output_text, report_text],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
