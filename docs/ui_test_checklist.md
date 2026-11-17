# Manual UI Test Checklist — Ticket Data Dashboard

**Why manual:** `streamlit.testing.v1.AppTest` in Streamlit 1.39.0 cannot set a file on `st.file_uploader`. The automated UI test (`tests/ui/test_app.py`) therefore covers only the no-upload state. The service layer behind every case below is covered automatically by `tests/unit/test_service.py`. This checklist confirms what the user actually sees.

**Setup:** follow README §5, then run `streamlit run src/ticket_dashboard/app.py` and open http://localhost:8501. Paths below are relative to `Day-04-Streamlit-Application-Basics/`. The sample data is Day 03's own file, `../Day-03-Python-Engineering-Practices-Exceptions-Testing/data/tickets.csv` (Day 04 has no copy); below it is called **Day 03's `tickets.csv`**.

| Tester | Date | Python / OS | Browser |
|---|---|---|---|
| | | | |

| ID | Steps | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|
| UI-01 | Open the app with no file selected. | Title "Ticket Data Dashboard". The sidebar shows the purpose, the 7 required columns and "Max file size: 5 MB". Blue info box: "Upload a ticket CSV to begin." No tabs, no error. | | |
| UI-02 | Upload Day 03's `tickets.csv`. | Warning: "3 of 10 rows were rejected. See the Data quality tab." Tabs in order: Preview, Analytics, Data quality. **Preview:** Rows 10, Columns 9, caption "10 rows x 9 columns", column-types table (`resolution_time_hours` decimal, `customer_rating` integer, `created_at` date, others text), 10 raw rows. **Analytics:** priority table urgent 1, high 2, medium 2, low 2, plus a bar chart whose bars are in the same order (urgent, high, medium, low), not alphabetical. Resolution table: technical 2 / 6.25 / 6.25; billing 1 / 3.0 / 3.0; account 1 / 2.0 / 2.0; unknown 1 / 1.5 / 1.5. **Data quality:** Rows read 10, Valid tickets 7, Rejected rows 3, Rejection rate 30.0%, Rejections by column "category: 1, customer: 2, description: 1", Valid tickets without resolution time 2. Rejected rows: lines 4, 7 and 9 with their problems. | | |
| UI-03 | Upload `tests/fixtures/empty.csv` (0 bytes). | Red error: "The uploaded file is empty. Choose a CSV file that has a header row and at least one ticket." No tabs, no traceback. | | |
| UI-04 | Upload `tests/fixtures/header_only.csv`. | Red error: "header_only.csv has a header row but no data rows. Add at least one ticket." No tabs. | | |
| UI-05 | Upload `tests/fixtures/missing_columns.csv`. | Red error: "missing_columns.csv is missing required column(s): category, created_at, customer, description, status. Found columns: id, priority. Add the missing column(s) to the header row." No tabs. | | |
| UI-06 | Upload `tests/fixtures/malformed_quote.csv`. | Red error: "CSV could not be parsed (unexpected end of data) (malformed_quote.csv, line 2). Check for an unbalanced or stray double quote, or binary content." No tabs. | | |
| UI-07 | Upload `tests/fixtures/all_rows_invalid.csv`. | Warning: "2 of 2 rows were rejected. See the Data quality tab." **Analytics:** info "No valid tickets to analyse." **Data quality:** Rejection rate 100.0%, Rejections by column "customer: 1, description: 1, priority: 1"; rejected lines 2 and 3. | | |
| UI-08 | Make a text file that is not CSV data (for example, a few lines of prose, or a copy of any `.txt` file), rename it to `notes.csv`, and upload it. | A red error message from the pipeline (for example, a missing-columns message naming `notes.csv`) and no tabs. No traceback. No local or temporary path is shown in the message. | | |
| UI-09 | Upload a `.csv` file larger than 5 MB (for example, Day 03's `tickets.csv` with about 70,000 copies of a data row appended). | Red error: "The file is larger than 5 MB. Upload a smaller CSV." No tabs. | | |
| UI-10 | With Day 03's `tickets.csv` loaded, switch between Preview, Analytics and Data quality several times. Watch the terminal running Streamlit. | The data stays the same on every tab. The terminal shows the three `stage=parse status=rejected` warning lines (lines 4, 7, 9) once, at upload, and no new ones while switching tabs, which shows the pipeline did not run again. | | |
| UI-11 | With Day 03's `tickets.csv` loaded, upload `tests/fixtures/all_rows_invalid.csv` in its place. | Every tab now shows the second file (2 rows, 0 valid). Nothing from the first file remains. | | |
| UI-12 | With a file loaded, remove it with the "x" next to the file name. | The page returns to the empty state from UI-01: "Upload a ticket CSV to begin.", no tabs, no warning. | | |
| UI-13 | Try to choose a file with another extension (for example, a `.txt` file) in the file picker or by drag-and-drop. | Streamlit refuses the file because only `.csv` is accepted. No processing happens. | | |
| UI-14 | Copy Day 03's `tickets.csv` to `copy_of_tickets.csv` in the Day 04 folder (same bytes, new name). Upload Day 03's `tickets.csv`, then upload `copy_of_tickets.csv` in its place. | After the second upload the three `stage=parse status=rejected` warnings appear again in the terminal (the new name is a new cache key) and the numbers are identical to UI-02. Delete the copy afterwards. | | |
| UI-15 | Upload the same Day 03's `tickets.csv` twice in a row (remove it, then upload it again) and compare every tab. | Every number, table and the chart order are exactly the same both times. | | |

**Notes for testers**

- UI-10 relies on the pipeline's WARNING log lines, which Python prints to the Streamlit terminal. If none appear even on the first upload, record that in Actual result and judge only whether the tabs keep the same data.
- To make the file for UI-09 in Git Bash: `cp ../Day-03-Python-Engineering-Practices-Exceptions-Testing/data/tickets.csv big.csv; for i in $(seq 1 70000); do echo "T002,Bob Smith,low,technical,closed,App crashes on startup,4.5,4,2024-01-16"; done >> big.csv`. Delete `big.csv` afterwards.
