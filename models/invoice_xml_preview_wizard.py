from lxml import etree

from odoo import fields, models
from odoo.tools import html_escape


class InvoiceXMLPreviewWizard(models.TransientModel):
    _name = 'invoice.xml.preview.wizard'
    _description = 'Invoice XML Preview'

    preview_html = fields.Html(string='Preview', sanitize=False, readonly=True)

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

    @staticmethod
    def build_preview_html(xml_content, xslt_content):
        if not xml_content:
            return '<div class="text-warning">Görüntülenecek XML içeriği bulunamadı.</div>'

        try:
            xml_doc = etree.fromstring(xml_content)
        except etree.XMLSyntaxError:
            escaped_xml = html_escape(
                xml_content.decode('utf-8', errors='replace') if isinstance(xml_content, (bytes, bytearray)) else str(xml_content)
            )
            return (
                '<div class="text-danger">XML içeriği okunamadı.</div>'
                '<pre style="white-space:pre-wrap;word-break:break-word;max-height:70vh;overflow:auto;padding:8px;">'
                f'{escaped_xml}'
                '</pre>'
            )

        if not xslt_content:
            escaped_xml = html_escape(etree.tostring(xml_doc, encoding='unicode', pretty_print=True))
            return (
                '<pre style="white-space:pre-wrap;word-break:break-word;max-height:70vh;overflow:auto;padding:8px;">'
                f'{escaped_xml}'
                '</pre>'
            )

        try:
            xsl_doc = etree.fromstring(xslt_content)
            transform = etree.XSLT(xsl_doc)
            html_result = transform(xml_doc)
            return str(html_result)
        except (etree.XMLSyntaxError, etree.XSLTError, ValueError):
            escaped_xml = html_escape(etree.tostring(xml_doc, encoding='unicode', pretty_print=True))
            return (
                '<div class="text-danger">XSLT önizleme sırasında hata oluştu. XML içeriği gösteriliyor.</div>'
                '<pre style="white-space:pre-wrap;word-break:break-word;max-height:70vh;overflow:auto;padding:8px;">'
                f'{escaped_xml}'
                '</pre>'
            )
