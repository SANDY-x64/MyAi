"""
MyAI Excel Candidate Management Engine
Automatically updates data/candidates.xlsx and data/candidates.csv with registered candidate details,
registration timestamps, last login timestamps, activity counts, and memories.
Uses openpyxl for formatted .xlsx spreadsheets and standard csv for universal compatibility.
"""

import sqlite3
import csv
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "myai.db"
EXCEL_PATH = DATA_DIR / "candidates.xlsx"
CSV_PATH = DATA_DIR / "candidates.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_all_candidates_data() -> List[Dict[str, Any]]:
    """Retrieve full candidate records from SQLite with aggregate conversation and memory counts."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check column existence safely
        cursor.execute("PRAGMA table_info(messages)")
        msg_cols = [c[1] for c in cursor.fetchall()]
        conv_sub = "(SELECT COUNT(DISTINCT conversation_id) FROM messages WHERE user_id = u.id)" if "user_id" in msg_cols else "0"

        cursor.execute("PRAGMA table_info(memories)")
        mem_cols = [c[1] for c in cursor.fetchall()]
        mem_sub = "(SELECT COUNT(*) FROM memories WHERE user_id = u.id)" if "user_id" in mem_cols else "0"

        # Query users with conversation and memory aggregates
        query = f"""
            SELECT
                u.id,
                u.username,
                COALESCE(u.full_name, u.username) AS full_name,
                COALESCE(u.email, 'Not provided') AS email,
                COALESCE(u.phone, 'Not provided') AS phone,
                COALESCE(u.role, 'Candidate') AS role,
                u.created_at,
                u.last_login_at,
                {conv_sub} AS total_conversations,
                {mem_sub} AS total_memories
            FROM users u
            ORDER BY u.id ASC
        """
        rows = cursor.execute(query).fetchall()

        candidates = []
        for r in rows:
            candidates.append({
                "id": r["id"],
                "username": r["username"],
                "full_name": r["full_name"],
                "email": r["email"],
                "phone": r["phone"],
                "role": r["role"],
                "created_at": r["created_at"] or "N/A",
                "last_login_at": r["last_login_at"] or r["created_at"] or "N/A",
                "total_conversations": r["total_conversations"],
                "total_memories": r["total_memories"],
                "status": "Active"
            })
        return candidates


def sync_candidates_to_excel() -> Dict[str, Any]:
    """
    Sync all registered candidates into data/candidates.xlsx and data/candidates.csv.
    Applies professional styling: custom headers, borders, colors, and auto-adjusted column widths.
    """
    candidates = get_all_candidates_data()

    # 1. Update CSV file for universal export
    try:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Candidate ID", "Username", "Full Name", "Email", "Phone",
                "Role / Track", "Registration Date", "Last Login Date",
                "Total Conversations", "Total Memories Saved", "Account Status"
            ])
            for c in candidates:
                writer.writerow([
                    c["id"], c["username"], c["full_name"], c["email"], c["phone"],
                    c["role"], c["created_at"], c["last_login_at"],
                    c["total_conversations"], c["total_memories"], c["status"]
                ])
    except Exception as exc:
        print(f"[ExcelManager] CSV write error: {exc}")

    # 2. Update formatted Excel (.xlsx) file
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Candidate Directory"

        # Enable grid lines
        ws.views.sheetView[0].showGridLines = True

        # Header Styles
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Segoe UI", size=14, bold=True, color="0F172A")
        sub_font = Font(name="Segoe UI", size=9, italic=True, color="64748B")

        data_font = Font(name="Segoe UI", size=10, color="1E293B")
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")

        thin_side = Side(border_style="thin", color="CBD5E1")
        cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        alt_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

        # Row 1: Title
        ws.merge_cells("A1:K1")
        title_cell = ws["A1"]
        title_cell.value = "MyAI - Candidate Roster & Personal Memory Register"
        title_cell.font = title_font
        title_cell.alignment = left_align
        ws.row_dimensions[1].height = 28

        # Row 2: Subtitle / Timestamp
        ws.merge_cells("A2:K2")
        sub_cell = ws["A2"]
        sub_cell.value = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Candidates: {len(candidates)}"
        sub_cell.font = sub_font
        sub_cell.alignment = left_align
        ws.row_dimensions[2].height = 18

        # Blank Row 3
        ws.row_dimensions[3].height = 8

        # Row 4: Column Headers
        headers = [
            "Candidate ID", "Username", "Full Name", "Email Address", "Phone Number",
            "Role / Purpose", "Registered At", "Last Login At",
            "Chats", "Memories", "Status"
        ]

        for col_idx, h in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = cell_border
        ws.row_dimensions[4].height = 26

        # Data Rows starting at Row 5
        for row_idx, c in enumerate(candidates, start=5):
            row_fill = alt_fill if row_idx % 2 == 0 else white_fill
            row_data = [
                (c["id"], center_align),
                (c["username"], left_align),
                (c["full_name"], left_align),
                (c["email"], left_align),
                (c["phone"], center_align),
                (c["role"], left_align),
                (str(c["created_at"]), center_align),
                (str(c["last_login_at"]), center_align),
                (c["total_conversations"], right_align),
                (c["total_memories"], right_align),
                (c["status"], center_align),
            ]

            for col_idx, (val, alignment) in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = data_font
                cell.fill = row_fill
                cell.alignment = alignment
                cell.border = cell_border

            ws.row_dimensions[row_idx].height = 20

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.row in [1, 2, 3]:
                    continue
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        wb.save(EXCEL_PATH)
        return {
            "success": True,
            "excel_path": str(EXCEL_PATH),
            "csv_path": str(CSV_PATH),
            "total_candidates": len(candidates)
        }
    except Exception as exc:
        print(f"[ExcelManager] Excel write error: {exc}")
        return {"success": False, "error": str(exc)}
