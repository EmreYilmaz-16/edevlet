import base64

from odoo import fields, models


class InvoiceXMLPreviewWizard(models.TransientModel):
    _name = 'invoice.xml.preview.wizard'
    _description = 'Invoice XML Preview'

    preview_html = fields.Html(string='Preview', sanitize=False, readonly=True)

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

    @staticmethod
    def build_preview_html(xml_content, xslt_content):
        xml_b64 = base64.b64encode(xml_content).decode('ascii')
        xslt_b64 = base64.b64encode(xslt_content).decode('ascii') if xslt_content else ''
        return f"""
<div id="preview_invoice" style="max-height:70vh;overflow:auto;padding:8px;"></div>
<script type="text/javascript">
(function () {{
    function decodeBase64Unicode(data) {{
        if (!data) {{
            return '';
        }}
        try {{
            return decodeURIComponent(Array.prototype.map.call(atob(data), function(c) {{
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }}).join(''));
        }} catch (error) {{
            return atob(data);
        }}
    }}

    function displayResult() {{
        var previewNode = document.getElementById('preview_invoice');
        if (!previewNode) {{
            return;
        }}

        var xmlText = decodeBase64Unicode('{xml_b64}');
        var xslText = decodeBase64Unicode('{xslt_b64}');

        if (!xslText) {{
            previewNode.innerHTML = '<pre style="white-space:pre-wrap;word-break:break-word;">' +
                (xmlText || '').replace(/[&<>]/g, function(ch) {{
                    return {{'&': '&amp;', '<': '&lt;', '>': '&gt;'}}[ch];
                }}) +
                '</pre>';
            return;
        }}

        try {{
            var parser = new DOMParser();
            var xml = parser.parseFromString(xmlText, 'text/xml');
            var xsl = parser.parseFromString(xslText, 'text/xml');
            var xsltProcessor = new XSLTProcessor();
            xsltProcessor.importStylesheet(xsl);
            var resultDocument = xsltProcessor.transformToFragment(xml, document);
            previewNode.innerHTML = '';
            previewNode.appendChild(resultDocument);
        }} catch (error) {{
            previewNode.innerHTML = '<div class="text-danger">XSLT önizleme sırasında hata oluştu.</div>' +
                '<pre style="white-space:pre-wrap;word-break:break-word;">' +
                (xmlText || '').replace(/[&<>]/g, function(ch) {{
                    return {{'&': '&amp;', '<': '&lt;', '>': '&gt;'}}[ch];
                }}) +
                '</pre>';
        }}
    }}

    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', displayResult);
    }} else {{
        displayResult();
    }}

    document.addEventListener('keydown', function(event) {{
        if (event.key === 'Escape') {{
            window.close();
        }}
    }});
}})();
</script>
"""
