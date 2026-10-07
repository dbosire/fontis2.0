import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .. import services

register = template.Library()


@register.simple_tag
def expiry_badge(status):
    """Badge for a services.expiry_status() code (valid / expiring / expired / ...)."""
    from core.templatetags.ui import status_badge

    label, tone, _ = services.STATUS_DISPLAY[status]
    return status_badge(label, tone)


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_NUMBERED = re.compile(r"^\d+\.\s+(.*)$")


def _inline(text):
    return _BOLD.sub(r"<strong>\1</strong>", escape(text))


def _table(rows):
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    cells = [r for r in cells if any(r) and not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
    if not cells:
        return ""
    head, body = cells[0], cells[1:]
    th = "".join(f'<th class="px-3 py-2 text-left font-medium bg-gray-50 dark:bg-slate-800/60 border border-gray-200 dark:border-slate-700">{_inline(c)}</th>' for c in head)
    trs = "".join(
        "<tr>" + "".join(f'<td class="px-3 py-2 align-top border border-gray-200 dark:border-slate-700">{_inline(c)}</td>' for c in row) + "</tr>"
        for row in body
    )
    return f'<div class="overflow-x-auto my-3"><table class="min-w-full text-sm"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


@register.filter
def procedure_body(text):
    """Renders a procedure's lightweight markup to safe HTML. Everything is escaped
    first; only these constructs produce tags: `## ` / `### ` headings, `- ` bullets,
    `1. ` numbered steps, `| a | b |` tables, `**bold**` and blank-line paragraphs."""
    html, para, items, item_tag, table = [], [], [], None, []

    def flush_para():
        if para:
            html.append(f'<p class="my-2">{_inline(" ".join(para))}</p>')
            para.clear()

    def flush_list():
        nonlocal item_tag
        if items:
            cls = "list-disc" if item_tag == "ul" else "list-decimal"
            lis = "".join(f"<li>{_inline(i)}</li>" for i in items)
            html.append(f'<{item_tag} class="{cls} pl-6 my-2 space-y-1">{lis}</{item_tag}>')
            items.clear()
        item_tag = None

    def flush_table():
        if table:
            html.append(_table(table))
            table.clear()

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("|"):
            flush_para(); flush_list()
            table.append(stripped)
            continue
        flush_table()
        if not stripped:
            flush_para(); flush_list()
        elif stripped.startswith("### "):
            flush_para(); flush_list()
            html.append(f'<h4 class="font-semibold mt-4 mb-1">{_inline(stripped[4:])}</h4>')
        elif stripped.startswith("## "):
            flush_para(); flush_list()
            html.append(f'<h3 class="text-base font-semibold mt-6 mb-1 pb-1 border-b border-gray-200 dark:border-slate-700">{_inline(stripped[3:])}</h3>')
        elif stripped.startswith("- "):
            flush_para()
            if item_tag not in (None, "ul"):
                flush_list()
            item_tag = "ul"
            items.append(stripped[2:])
        elif _NUMBERED.match(stripped):
            flush_para()
            if item_tag not in (None, "ol"):
                flush_list()
            item_tag = "ol"
            items.append(_NUMBERED.match(stripped).group(1))
        else:
            flush_list()
            para.append(stripped)
    flush_para(); flush_list(); flush_table()
    return mark_safe("\n".join(html))
