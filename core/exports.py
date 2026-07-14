from django.http import HttpResponse
from django.template.loader import render_to_string
from openpyxl import Workbook


def build_xlsx(headers, rows, filename="export.xlsx", sheet_title="Sheet1"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(headers)
    for row in rows:
        ws.append(row)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


def render_pdf(template_name, context, filename="export.pdf"):
    from xhtml2pdf import pisa  # imported lazily; only the export views need PDF rendering

    html_string = render_to_string(template_name, context)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    pisa.CreatePDF(html_string, dest=response)
    return response
