"""Download and parse GPO Bill Status XML for lawmaking measures."""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from lxml import etree

from .config import (
    BILLSTATUS_ZIP,
    CACHE_DIR,
    INCORPORATION_PHRASES,
    INCORPORATION_REL_TYPES,
    LAWMAKING_TYPES,
    TYPE_DISPLAY,
)
from .http_util import download_file



_BILL_MENTION = re.compile(
    r"\b(H\.?R\.?|S\.|H\.?J\.?\s*RES\.?|S\.?J\.?\s*RES\.?)\s*(\d+)\b",
    re.IGNORECASE,
)


def zip_url(congress: int, bill_type: str) -> str:
    return BILLSTATUS_ZIP.format(congress=congress, bill_type=bill_type.lower())


def zip_path(congress: int, bill_type: str) -> Path:
    return CACHE_DIR / "billstatus" / f"BILLSTATUS-{congress}-{bill_type.lower()}.zip"


def download_congress(congress: int, *, force: bool = False) -> list[Path]:
    paths = []
    for bill_type in LAWMAKING_TYPES:
        dest = zip_path(congress, bill_type)
        url = zip_url(congress, bill_type)
        print(f"Downloading {congress} {bill_type.upper()} …")
        download_file(url, dest, force=force)
        size_mb = dest.stat().st_size / 1e6
        print(f"  cached {dest.name} ({size_mb:.1f} MB)")
        paths.append(dest)
    return paths


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _child_text(el: etree._Element | None, name: str) -> str:
    if el is None:
        return ""
    for child in el:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _find(el: etree._Element, name: str) -> etree._Element | None:
    for child in el:
        if _local(child.tag) == name:
            return child
    return None


def _findall(el: etree._Element, name: str) -> list[etree._Element]:
    return [child for child in el if _local(child.tag) == name]


def _walk(el: etree._Element, name: str) -> list[etree._Element]:
    found = []
    for child in el.iter():
        if _local(child.tag) == name:
            found.append(child)
    return found


def normalize_type(raw: str) -> str:
    key = re.sub(r"\s+", "", (raw or "").upper())
    key = key.replace("JOINTRESOLUTION", "JRES")
    aliases = {
        "HR": "HR",
        "H.R.": "HR",
        "H.R": "HR",
        "S": "S",
        "S.": "S",
        "HJRES": "HJRES",
        "H.J.RES.": "HJRES",
        "H.J.RES": "HJRES",
        "SJRES": "SJRES",
        "S.J.RES.": "SJRES",
        "S.J.RES": "SJRES",
    }
    if key in aliases:
        return aliases[key]
    if key.replace(".", "") in TYPE_DISPLAY:
        return TYPE_DISPLAY[key.replace(".", "")]
    compact = key.replace(".", "")
    return TYPE_DISPLAY.get(compact.lower(), compact)


def bill_id(congress: int | str, bill_type: str, number: str | int) -> str:
    return f"{int(congress)}-{normalize_type(bill_type)}-{int(number)}"


def _became_law(bill_el: etree._Element, latest_action: str) -> tuple[bool, str]:
    laws = _find(bill_el, "laws")
    if laws is not None:
        items = _findall(laws, "item")
        if items:
            first = items[0]
            kind = _child_text(first, "type")
            number = _child_text(first, "number")
            label = " ".join(p for p in (kind, number) if p)
            return True, label
    text = latest_action.lower()
    if "became public law" in text or "became private law" in text:
        return True, latest_action
    for action in _walk(bill_el, "item"):
        atype = _child_text(action, "type")
        atext = _child_text(action, "text")
        if atype == "BecameLaw" or "became public law" in atext.lower():
            return True, atext
    return False, ""


def _related(bill_el: etree._Element) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    block = _find(bill_el, "relatedBills")
    if block is None:
        return out
    for item in _findall(block, "item"):
        rel_congress = _child_text(item, "congress")
        rel_number = _child_text(item, "number")
        rel_type = _child_text(item, "type")
        if not (rel_congress and rel_number and rel_type):
            continue
        ntype = normalize_type(rel_type)
        if ntype not in {"HR", "S", "HJRES", "SJRES"}:
            continue
        details = _find(item, "relationshipDetails")
        rel_types: list[str] = []
        if details is not None:
            for det in _findall(details, "item"):
                rel_types.append(_child_text(det, "type"))
        if not rel_types:
            rel_types = ["Related bill"]
        for rel_type_label in rel_types:
            out.append(
                {
                    "related_id": bill_id(rel_congress, ntype, rel_number),
                    "rel_type": rel_type_label,
                }
            )
    return out


def _notes_and_actions(bill_el: etree._Element) -> str:
    chunks: list[str] = []
    for note in _walk(bill_el, "text"):
        if note.text:
            chunks.append(note.text)
    return "\n".join(chunks)


def parse_bill_xml(raw: bytes) -> dict[str, Any] | None:
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return None
    bill_el = root if _local(root.tag) == "bill" else _find(root, "bill")
    if bill_el is None:
        return None

    congress = _child_text(bill_el, "congress")
    number = _child_text(bill_el, "number") or _child_text(bill_el, "billNumber")
    btype = _child_text(bill_el, "type") or _child_text(bill_el, "billType")
    if not (congress and number and btype):
        return None
    ntype = normalize_type(btype)
    if ntype not in {"HR", "S", "HJRES", "SJRES"}:
        return None

    sponsors = _find(bill_el, "sponsors")
    sponsor_id = ""
    sponsor_name = ""
    if sponsors is not None:
        items = _findall(sponsors, "item")
        if items:
            first = items[0]
            sponsor_id = _child_text(first, "bioguideId")
            if not sponsor_id:
                ids = _find(first, "identifiers")
                sponsor_id = _child_text(ids, "bioguideId")
            sponsor_name = _child_text(first, "fullName") or " ".join(
                p
                for p in (
                    _child_text(first, "firstName"),
                    _child_text(first, "lastName"),
                )
                if p
            )

    if not sponsor_id:
        return None

    latest = _find(bill_el, "latestAction")
    latest_text = _child_text(latest, "text") if latest is not None else ""
    became, law_cite = _became_law(bill_el, latest_text)
    title = _child_text(bill_el, "title")
    policy = _find(bill_el, "policyArea")
    policy_name = _child_text(policy, "name") if policy is not None else ""

    return {
        "bill_id": bill_id(congress, ntype, number),
        "congress": int(congress),
        "bill_type": ntype,
        "number": int(number),
        "title": title,
        "policy_area": policy_name,
        "sponsor_bioguide": sponsor_id,
        "sponsor_name": sponsor_name,
        "introduced_date": _child_text(bill_el, "introducedDate"),
        "latest_action": latest_text,
        "became_law": became,
        "law_citation": law_cite,
        "related": _related(bill_el),
        "notes_blob": _notes_and_actions(bill_el),
    }


def parse_zip(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        for name in names:
            parsed = parse_bill_xml(zf.read(name))
            if parsed:
                rows.append(parsed)
    return rows


def load_bills(congresses: Iterable[int], *, force: bool = False) -> list[dict[str, Any]]:
    bills: list[dict[str, Any]] = []
    for congress in congresses:
        download_congress(int(congress), force=force)
        for bill_type in LAWMAKING_TYPES:
            path = zip_path(int(congress), bill_type)
            print(f"Parsing {path.name} …")
            parsed = parse_zip(path)
            print(f"  {len(parsed):,} lawmaking measures with a primary sponsor")
            bills.extend(parsed)
    return bills


def mention_to_id(congress: int, match: re.Match[str]) -> str | None:
    raw_type, number = match.group(1), match.group(2)
    compact = re.sub(r"[\s.]+", "", raw_type.upper())
    mapping = {"HR": "HR", "S": "S", "HJRES": "HJRES", "SJRES": "SJRES"}
    ntype = mapping.get(compact)
    if not ntype:
        return None
    return bill_id(congress, ntype, number)


def infer_incorporation_from_text(
    congress: int, notes_blob: str, enacted_ids: set[str], self_id: str
) -> str | None:
    """If notes/actions say the bill was incorporated into an enacted measure, return that id."""
    lower = notes_blob.lower()
    if not any(p in lower for p in INCORPORATION_PHRASES):
        return None
    for match in _BILL_MENTION.finditer(notes_blob):
        other = mention_to_id(congress, match)
        if other and other != self_id and other in enacted_ids:
            return other
    return None


def mark_incorporation(bills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Second pass: credit a bill if a qualifying related vehicle became law.

    Relationships are recorded on *either* bill. An omnibus that became law
    often lists the source measures as "Public law contains the text"; the
    source measures may or may not point back. Walk both directions.
    """
    enacted_ids = {b["bill_id"] for b in bills if b["became_law"]}

    reverse: dict[str, list[tuple[str, str]]] = {}
    for bill in bills:
        if not bill["became_law"]:
            continue
        for rel in bill.get("related") or []:
            label = (rel.get("rel_type") or "").strip().lower()
            other = rel.get("related_id")
            if other and other != bill["bill_id"] and label in INCORPORATION_REL_TYPES:
                reverse.setdefault(other, []).append((bill["bill_id"], rel["rel_type"]))

    for bill in bills:
        via: list[str] = []
        rel_labels: list[str] = []
        for rel in bill.get("related") or []:
            label = (rel.get("rel_type") or "").strip().lower()
            other = rel.get("related_id")
            if (
                other
                and other != bill["bill_id"]
                and other in enacted_ids
                and label in INCORPORATION_REL_TYPES
            ):
                via.append(other)
                rel_labels.append(rel["rel_type"])
        for enacted_id, label in reverse.get(bill["bill_id"], []):
            via.append(enacted_id)
            rel_labels.append(f"{label} (from enacted vehicle)")
        text_hit = infer_incorporation_from_text(
            bill["congress"], bill.get("notes_blob") or "", enacted_ids, bill["bill_id"]
        )
        if text_hit:
            via.append(text_hit)
            rel_labels.append("notes/actions")

        seen: set[str] = set()
        unique_via = []
        for vid in via:
            if vid not in seen:
                seen.add(vid)
                unique_via.append(vid)

        incorporated = (not bill["became_law"]) and bool(unique_via)
        bill["incorporated"] = incorporated
        bill["related_enacted_ids"] = ";".join(unique_via)
        bill["incorporation_basis"] = ";".join(dict.fromkeys(rel_labels))
        bill["enacted_including"] = bool(bill["became_law"] or incorporated)
    return bills
