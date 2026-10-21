"""Parse the NBA's official injury report PDFs into one row per listed player.

Three layouts appear across 2018-19 to 2025-26:

* 2018-19: Game Date, Game Time, Matchup, Team, Player Name, Category, Reason, Current Status, Previous Status.
* 2019-20 to 2024-25: Game Date, Game Time, Matchup, Team, Player Name, Current Status, Reason
  ("Injury/Illness - Left Ankle; Sprain").
* From the 2023 playoffs on: the same columns, but a long reason wraps onto two lines centred on the
  player's line.

Text extraction alone mixes those wrapped lines up, so the parser works from word positions: column
edges come from the header line, every player row is anchored by its status word (Out, Questionable,
Doubtful, Probable, Available), and every other fragment belongs to the nearest anchor. Date, time,
matchup and team are printed once per group, so they carry forward until the next one. A reason that
wraps at the foot of a page goes on at the top of the next one, where the nearest anchor is the wrong
row; those words are given back afterwards (``_rejoin_wrapped``).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pdfplumber

from . import teams

STATUSES = {"Out", "Questionable", "Doubtful", "Probable", "Available"}
GROUP_COLUMNS = ("game_date", "game_time", "matchup", "team")
ROW_COLUMNS = ("player", "category", "reason", "previous")
FOOTER = re.compile(r"^Page\s*\d+\s*of\s*\d+$")
STAMP = re.compile(r"Injury Report:\s*(\d{2}/\d{2}/\d{2})\s*(\d{1,2}:\d{2})\s*([AP]M)")
MATCHUP = re.compile(r"^([A-Z]{2,3})@([A-Z]{2,3})$")
# every reason opens with its category, so words in front of one are the end of the reason before
REASON_START = re.compile(r"Injury/Illness|G League|Health and Safety|Not [Ww]ith Team|Personal Reasons|Rest\b|"
                          r"Return to Competition|League Suspension|Trade Pending|Coach'?s Decision|Concussion Protocol|"
                          r"Ineligible [Tt]o Play|Team Suspension")


def _header_columns(words: list[dict]) -> tuple[float, list[tuple[float, str]]] | None:
    """(header line top, [(left edge, column)]) for the page, or None when the page has no header."""
    anchor = next((w for w in words if w["text"] == "Matchup"), None)
    if anchor is None:
        return None
    line = sorted((w for w in words if abs(w["top"] - anchor["top"]) < 3), key=lambda w: w["x0"])
    columns, i = [], 0
    while i < len(line):
        text, nxt = line[i]["text"], line[i + 1]["text"] if i + 1 < len(line) else ""
        x = line[i]["x0"]
        if text in ("Game", "GameDate", "GameTime"):
            kind = "game_date" if (text == "GameDate" or nxt == "Date") else "game_time"
            columns.append((x, kind))
            i += 1 if text != "Game" else 2
            continue
        name = {"Matchup": "matchup", "Team": "team", "Category": "category", "Reason": "reason"}.get(text)
        if name is None and text.startswith("Player"):
            name = "player"
        if name is None and text.startswith("Current"):
            name = "status"
        if name is None and text.startswith("Previous"):
            name = "previous"
        if name:
            columns.append((x, name))
        i += 1
    return anchor["top"], columns


def _column(x0: float, columns: list[tuple[float, str]]) -> str | None:
    found = None
    for left, name in columns:
        if x0 >= left - 4:
            found = name
    return found


def _lines(words: list[dict], tolerance: float = 2.0) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tolerance:
            lines[-1].append(w)
        else:
            lines.append([w])
    return lines


def _join(fragments: list[dict]) -> str:
    return " ".join(w["text"] for w in sorted(fragments, key=lambda w: (round(w["top"]), w["x0"]))).strip()


def parse_pdf(path: str | Path) -> dict:
    """{'stamp': ..., 'rows': [...], 'not_submitted': [...], 'problems': [...]} for one report."""
    path = Path(path)
    out: dict = dict(file=path.name, stamp=None, rows=[], not_submitted=[], problems=[])
    state = dict(game_date=None, game_time=None, matchup=None, away=None, home=None, team=None)
    columns: list[tuple[float, str]] | None = None
    items: list[dict] = []   # the rows and not-submitted lines in order, with their reason text
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=2)
            if out["stamp"] is None:
                head = " ".join(w["text"] for w in words[:12])
                m = STAMP.search(head)
                if m:
                    out["stamp"] = datetime.strptime(" ".join(m.groups()), "%m/%d/%y %I:%M %p").isoformat()
            header = _header_columns(words)
            if header is not None:
                header_top, columns = header
                words = [w for w in words if w["top"] > header_top + 5]
            elif columns is None:
                out["problems"].append(f"page {page_no}: no header")
                continue
            body = [line for line in _lines(words)
                    if not FOOTER.match(" ".join(w["text"] for w in line))
                    and not " ".join(w["text"] for w in line).startswith("Injury Report:")]   # title repeated on later pages

            # Anchors: player rows (a status word in the status column) and "NOT YET SUBMITTED" lines.
            anchors = []
            for line in body:
                status = [w for w in line if _column(w["x0"], columns) == "status" and w["text"] in STATUSES]
                text = " ".join(w["text"] for w in line)
                if status:
                    anchors.append(dict(kind="row", y=(status[0]["top"] + status[0]["bottom"]) / 2,
                                        status=status[0]["text"], fragments=[], skip=status[0]))
                elif "SUBMITTED" in text.replace(" ", ""):
                    anchors.append(dict(kind="not_submitted", y=(line[0]["top"] + line[0]["bottom"]) / 2,
                                        status=None, fragments=[], skip=None, line=line))
            if not anchors:
                continue
            for line in body:
                for w in line:
                    if any(w is a["skip"] for a in anchors):
                        continue
                    y = (w["top"] + w["bottom"]) / 2
                    nearest = min(anchors, key=lambda a: (abs(a["y"] - y), a["y"]))
                    if nearest["kind"] == "not_submitted" and w["text"] in ("NOT", "YET", "SUBMITTED", "NOTYETSUBMITTED"):
                        continue
                    nearest["fragments"].append(w)

            for anchor in sorted(anchors, key=lambda a: a["y"]):
                cells: dict[str, list[dict]] = {}
                for w in anchor["fragments"]:
                    cells.setdefault(_column(w["x0"], columns) or "?", []).append(w)
                _apply_group(state, cells, out["problems"], page_no)
                if anchor["kind"] == "not_submitted":
                    out["not_submitted"].append(dict(game_date=state["game_date"], matchup=state["matchup"], team=state["team"]))
                    items.append(dict(kind="not_submitted", page=page_no, reason=_join(cells.get("reason", []))))
                    continue
                category = _join(cells.get("category", []))
                reason = _join(cells.get("reason", []))
                if category:   # 2018-19 layout: fold the category into the reason text
                    reason = category if reason in ("", "-") else f"{category} - {reason}"
                row = dict(
                    game_date=state["game_date"], game_time=state["game_time"], matchup=state["matchup"],
                    team=state["team"], player=_join(cells.get("player", [])), status=anchor["status"],
                    reason=reason, previous_status=_join(cells.get("previous", [])) or None, page=page_no)
                out["rows"].append(row)
                items.append(dict(kind="row", page=page_no, reason=reason, row=row))
    _rejoin_wrapped(items)
    for item in items:
        if item["kind"] == "row":
            item["row"]["reason"] = item["reason"]
    return out


def _rejoin_wrapped(items: list[dict]) -> None:
    """Give a reason back the words the report wrapped onto the next page.

    They land on the page's first row ("Tear Injury/Illness - N/A; Concussion" after "Injury/Illness - Right Achilles
    Tendon;"), or on a "NOT YET SUBMITTED" line, which has no reason of its own and would drop them. ``items`` are
    the report's rows and not-submitted lines in order, as {kind, page, reason}; their reasons change in place.
    """
    for i, item in enumerate(items):
        before = items[i - 1] if i else None
        after = items[i + 1] if i + 1 < len(items) else None
        text = item["reason"]
        if item["kind"] == "not_submitted":
            if text and REASON_START.match(text) and after and after["kind"] == "row" and after["page"] == item["page"]:
                after["reason"] = f"{text} {after['reason']}".strip()   # the opening line of the row below
            elif text and before and before["kind"] == "row":
                before["reason"] = f"{before['reason']} {text}".strip()
            item["reason"] = ""
        elif before and before["kind"] == "row" and before["page"] != item["page"]:
            start = REASON_START.search(text)
            # an available player's reason is a bare dash, with the wrapped words in front of it
            cut = start.start() if start else (len(text) - 1 if re.fullmatch(r".*\S\s+-", text) else 0)
            if cut:
                before["reason"] = f"{before['reason']} {text[:cut].strip()}".strip()
                item["reason"] = text[cut:]


def _apply_group(state: dict, cells: dict, problems: list, page_no: int) -> None:
    if "game_date" in cells:
        m = re.search(r"(\d{2}/\d{2}/\d{4})", _join(cells["game_date"]))
        if m:
            state["game_date"] = datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat()
    if "game_time" in cells:
        m = re.search(r"(\d{1,2}:\d{2})", _join(cells["game_time"]))
        if m:
            state["game_time"] = m.group(1)
    if "matchup" in cells:
        m = MATCHUP.match(_join(cells["matchup"]).replace(" ", ""))
        if m:
            state.update(matchup=m.group(0), away=m.group(1), home=m.group(2), team=None)
        else:
            problems.append(f"page {page_no}: unreadable matchup {_join(cells['matchup'])!r}")
    if "team" in cells:
        candidates = [c for c in (state["away"], state["home"]) if c]
        code = teams.resolve_name(_join(cells["team"]), candidates or None)
        if code:
            state["team"] = code
        else:
            problems.append(f"page {page_no}: unknown team {_join(cells['team'])!r}")
