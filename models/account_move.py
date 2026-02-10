import base64
import copy
import uuid
import xml.etree.ElementTree as ET

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import file_path

PROFILE_TYPES = [
    ('TICARIFATURA', 'TICARIFATURA'),
    ('IHRACAT', 'IHRACAT'),
    ('TEMELFATURA', 'TEMELFATURA'),
    ('YOLCUBERABERFATURA', 'YOLCUBERABERFATURA'),
    ('BEDELSIZIHRACAT', 'BEDELSIZIHRACAT'),
    ('KAMU', 'KAMU'),
    ('ENERJI', 'ENERJI'),
    ('ILAC_TIBBICIHAZ', 'ILAC_TIBBICIHAZ'),
    ('MIKROIHRACAT', 'MIKROIHRACAT'),
]

INVOICE_TYPE_CODES = [
    ('SATIS', 'SATIS'),
    ('IADE', 'IADE'),
    ('IHRACKAYITLI', 'IHRACKAYITLI'),
    ('KONAKLAMAVERGISI', 'KONAKLAMAVERGISI'),
    ('SGK', 'SGK'),
    ('TEVKIFATIADE', 'TEVKIFATIADE'),
    ('SARJ', 'SARJ'),
    ('SARJANLIK', 'SARJANLIK'),
    ('TEKNOLOJIDESTEK', 'TEKNOLOJIDESTEK'),
]

UBL_XML_NAMESPACES = {
    '': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    'xades': 'http://uri.etsi.org/01903/v1.3.2#',
    'udt': 'urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2',
    'ccts': 'urn:un:unece:uncefact:documentation:2',
    'ubltr': 'urn:oasis:names:specification:ubl:schema:xsd:TurkishCustomizationExtensionComponents',
    'qdt': 'urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    profile_type = fields.Selection(
        PROFILE_TYPES,
        string='Profile Type',
        default='TICARIFATURA',
    )
    invoice_type_code = fields.Selection(
        INVOICE_TYPE_CODES,
        string='Invoice Type Code',
        default='SATIS',
    )

    @api.constrains('profile_type', 'move_type')
    def _check_profile_type_required(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund') and not move.profile_type:
                raise ValidationError(_('Profile Type is required for customer invoices.'))

    @api.constrains('invoice_type_code', 'move_type')
    def _check_invoice_type_code_required(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund') and not move.invoice_type_code:
                raise ValidationError(_('Invoice Type Code is required for customer invoices.'))

    def action_download_invoice_xml(self):
        self.ensure_one()
        xml_content = self._generate_invoice_xml_content()
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name or 'invoice'}.xml",
            'type': 'binary',
            'datas': base64.b64encode(xml_content),
            'mimetype': 'application/xml',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'self',
        }

    def action_preview_invoice_xml(self):
        self.ensure_one()
        xml_content = self._generate_invoice_xml_content()
        wizard = self.env['invoice.xml.preview.wizard'].create({
            'preview_html': self.env['invoice.xml.preview.wizard'].build_preview_html(
                xml_content,
                self._get_invoice_xslt_bytes(),
            ),
        })
        return {
            'name': _('Fatura XML Önizleme'),
            'type': 'ir.actions.act_window',
            'res_model': 'invoice.xml.preview.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def _generate_invoice_xml_content(self):
        module_path = __name__.split('.')
        module_name = (
            module_path[2]
            if len(module_path) >= 3 and module_path[0] == 'odoo' and module_path[1] == 'addons'
            else module_path[0]
        )
        xml_path = file_path(f"{module_name}/ornek_xml.xml")
        if not xml_path:
            raise ValidationError(_('Sample XML file could not be found.'))
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError as error:
            raise ValidationError(_('Sample XML file is not valid.')) from error
        root = tree.getroot()
        nsmap = UBL_XML_NAMESPACES
        self._register_xml_namespaces(nsmap)

        currency = self.currency_id or self.company_id.currency_id
        currency_code = currency and currency.name or 'TRY'
        issue_date = self.invoice_date or fields.Date.context_today(self)
        issue_time_dt = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        issue_time = issue_time_dt.strftime('%H:%M:%S') if hasattr(issue_time_dt, 'strftime') else '00:00:00'
        uuid_value = str(uuid.uuid4())

        # Sadece section ve note satırlarını filtrele, ürün satırlarını al
        invoice_lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type not in ('line_section', 'line_note')
        )

        self._set_xml_text(root, 'cbc:ID', self.name or '', nsmap)
        self._set_xml_text(root, 'cbc:ProfileID', self.profile_type or 'TICARIFATURA', nsmap)
        self._set_xml_text(root, 'cbc:InvoiceTypeCode', self.invoice_type_code or 'SATIS', nsmap)
        self._set_xml_text(root, 'cbc:DocumentCurrencyCode', currency_code, nsmap)
        self._set_xml_text(root, 'cbc:PaymentCurrencyCode', currency_code, nsmap)
        self._set_xml_text(root, 'cbc:UUID', uuid_value, nsmap)
        self._set_xml_text(root, 'cbc:IssueDate', fields.Date.to_string(issue_date), nsmap)
        self._set_xml_text(root, 'cbc:IssueTime', issue_time, nsmap)
        self._set_xml_text(root, 'cbc:LineCountNumeric', str(len(invoice_lines)), nsmap)
        
        if self.invoice_origin:
            order_ref = root.find('cac:OrderReference', nsmap)
            self._set_xml_text(order_ref, 'cbc:ID', self.invoice_origin, nsmap)
            self._set_xml_text(order_ref, 'cbc:IssueDate', fields.Date.to_string(issue_date), nsmap)
        else:
            order_ref = root.find('cac:OrderReference', nsmap)
            if order_ref is not None:
                root.remove(order_ref)
        note_nodes = root.findall('cbc:Note', nsmap)
        if note_nodes:
            issue_time_note = issue_time_dt.strftime('%H:%M') if hasattr(issue_time_dt, 'strftime') else ''
            note_nodes[0].text = issue_time_note
            if len(note_nodes) > 1:
                note_nodes[1].text = issue_date.strftime('%d-%m-%Y') if hasattr(issue_date, 'strftime') else ''
            if len(note_nodes) > 2:
                note_nodes[2].text = self.invoice_user_id.name or self.create_uid.name or ''
            if len(note_nodes) > 3:
                for extra_node in note_nodes[3:]:
                    root.remove(extra_node)

        amount_in_words = self._get_amount_in_words(currency)
        if amount_in_words:
            for doc_ref in root.findall('cac:AdditionalDocumentReference', nsmap):
                doc_type = doc_ref.find('cbc:DocumentType', nsmap)
                if doc_type is None or not doc_type.text:
                    continue
                doc_type_value = doc_type.text.strip()
                if doc_type_value in ('TR_NET_STR', 'TOTAL_NET_STR'):
                    self._set_xml_text(doc_ref, 'cbc:ID', amount_in_words, nsmap)
                    self._set_xml_text(doc_ref, 'cbc:IssueDate', fields.Date.to_string(issue_date), nsmap)
                elif doc_type_value == 'PAYABLEAMOUNT':
                    self._set_xml_text(doc_ref, 'cbc:ID', self._float_to_str(self.amount_total, digits=2), nsmap)
                    self._set_xml_text(doc_ref, 'cbc:IssueDate', fields.Date.to_string(issue_date), nsmap)

        self._populate_party_block(
            root.find('cac:AccountingSupplierParty', nsmap),
            self.company_id.partner_id,
            nsmap,
        )
        self._populate_party_block(
            root.find('cac:AccountingCustomerParty', nsmap),
            self.partner_id.commercial_partner_id,
            nsmap,
        )

        self._populate_invoice_lines(root, invoice_lines, currency, currency_code, nsmap)
        self._update_totals(root, currency, currency_code, invoice_lines, nsmap)
        self._apply_xslt_attachment(root, nsmap)

        return ET.tostring(root, encoding='utf-8', xml_declaration=True)

    def _get_edevlet_integration(self):
        self.ensure_one()
        Integration = self.env['edevlet.integration']
        integration = Integration.search([('company_code', '=', self.company_id.id)], limit=1)
        if not integration:
            integration = Integration.search([('type', '=', '1')], limit=1)
        if not integration:
            integration = Integration.search([], limit=1)
        return integration

    def _apply_xslt_attachment(self, root, nsmap):
        integration = self._get_edevlet_integration()
        xslt_base64 = self._get_invoice_xslt_base64(integration=integration)
        issue_date = self.invoice_date or fields.Date.context_today(self)
        for doc_ref in root.findall('cac:AdditionalDocumentReference', nsmap):
            doc_type = doc_ref.find('cbc:DocumentType', nsmap)
            if doc_type is None or not doc_type.text:
                continue
            if doc_type.text.strip().upper() != 'XSLT':
                continue
            # ID ve IssueDate alanlarını doldur
            invoice_number = self.name or f'DRAFT-{self.id}'
            self._set_xml_text(doc_ref, 'cbc:ID', invoice_number, nsmap)
            self._set_xml_text(doc_ref, 'cbc:IssueDate', fields.Date.to_string(issue_date), nsmap)
            # Base64 içeriğini ekle
            embedded = doc_ref.find('cac:Attachment/cbc:EmbeddedDocumentBinaryObject', nsmap)
            if embedded is None:
                continue
            if xslt_base64:
                embedded.text = xslt_base64
                if integration and integration.xslt_file_name:
                    embedded.set('filename', integration.xslt_file_name)

    def _get_invoice_xslt_base64(self, integration=None):
        integration = integration or self._get_edevlet_integration()
        xslt_base64 = None
        if integration and integration.xslt_base64:
            xslt_base64 = integration.xslt_base64
            if isinstance(xslt_base64, bytes):
                xslt_base64 = xslt_base64.decode()
        return xslt_base64

    def _get_invoice_xslt_bytes(self):
        xslt_base64 = self._get_invoice_xslt_base64()
        if not xslt_base64:
            return b''
        return base64.b64decode(xslt_base64)

    def _populate_party_block(self, party_record, partner, nsmap):
        if party_record is None or not partner:
            return
        party = party_record.find('cac:Party', nsmap)
        if party is None:
            party = party_record
        self._set_xml_text(party, 'cbc:WebsiteURI', partner.website or '', nsmap)

        identification = party.find('cac:PartyIdentification', nsmap)
        if identification is not None:
            tax_id = partner.vergi_no or partner.vat or ''
            id_node = identification.find('cbc:ID', nsmap)
            if id_node is not None:
                id_node.text = tax_id
                if tax_id:
                    scheme = 'VKN' if partner.is_company else 'TCKN'
                    id_node.set('schemeID', scheme)

        self._set_xml_text(party, 'cac:PartyName/cbc:Name', partner.name or '', nsmap)

        address = party.find('cac:PostalAddress', nsmap)
        if address is not None:
            self._set_xml_text(address, 'cbc:StreetName', partner.street or '', nsmap)
            self._set_xml_text(address, 'cbc:BuildingNumber', partner.bina_numarasi or '', nsmap)
            self._set_xml_text(address, 'cbc:CitySubdivisionName', partner.city or '', nsmap)
            self._set_xml_text(address, 'cbc:CityName', partner.city or '', nsmap)
            self._set_xml_text(address, 'cbc:PostalZone', partner.zip or '', nsmap)
            region = partner.state_id.name if partner.state_id else ''
            self._set_xml_text(address, 'cbc:Region', region, nsmap)
            country_el = address.find('cac:Country', nsmap)
            self._set_xml_text(country_el, 'cbc:Name', partner.country_id.name if partner.country_id else '', nsmap)

        tax_scheme = party.find('cac:PartyTaxScheme/cac:TaxScheme', nsmap)
        self._set_xml_text(tax_scheme, 'cbc:Name', partner.vergi_dairesi or '', nsmap)

        contact = party.find('cac:Contact', nsmap)
        if contact is not None:
            phone = partner.phone or partner.mobile or ''
            self._set_xml_text(contact, 'cbc:Telephone', phone, nsmap)
            self._set_xml_text(contact, 'cbc:ElectronicMail', partner.email or '', nsmap)

    def _populate_invoice_lines(self, root, invoice_lines, currency, currency_code, nsmap):
        template = root.find('cac:InvoiceLine', nsmap)
        if template is not None:
            template = copy.deepcopy(template)
        else:
            template = self._build_invoice_line_template(currency_code)
        
        # İlk olarak mevcut satırları temizle
        for existing in root.findall('cac:InvoiceLine', nsmap):
            root.remove(existing)

        if not invoice_lines:
            return

        # Satırları LegalMonetaryTotal'dan sonra ekle (UBL standart sırasına göre)
        monetary_total = root.find('cac:LegalMonetaryTotal', nsmap)
        insert_position = None
        if monetary_total is not None:
            insert_position = list(root).index(monetary_total) + 1
        
        for index, line in enumerate(invoice_lines, start=1):
            line_element = copy.deepcopy(template)
            self._fill_invoice_line(line_element, line, index, currency, currency_code, nsmap)
            
            if insert_position is not None:
                # Her satır eklendiğinde pozisyonu artır
                root.insert(insert_position + index - 1, line_element)
            else:
                root.append(line_element)

    def _build_invoice_line_template(self, currency_code):
        nsmap = UBL_XML_NAMESPACES
        line_el = ET.Element(f"{{{nsmap['cac']}}}InvoiceLine")
        ET.SubElement(line_el, f"{{{nsmap['cbc']}}}ID")
        ET.SubElement(line_el, f"{{{nsmap['cbc']}}}Note")
        ET.SubElement(line_el, f"{{{nsmap['cbc']}}}InvoicedQuantity", unitCode='C62')
        ET.SubElement(line_el, f"{{{nsmap['cbc']}}}LineExtensionAmount", currencyID=currency_code)
        allowance_charge = ET.SubElement(line_el, f"{{{nsmap['cac']}}}AllowanceCharge")
        ET.SubElement(allowance_charge, f"{{{nsmap['cbc']}}}ChargeIndicator")
        ET.SubElement(allowance_charge, f"{{{nsmap['cbc']}}}MultiplierFactorNumeric")
        ET.SubElement(allowance_charge, f"{{{nsmap['cbc']}}}Amount", currencyID=currency_code)
        ET.SubElement(allowance_charge, f"{{{nsmap['cbc']}}}BaseAmount", currencyID=currency_code)
        tax_total = ET.SubElement(line_el, f"{{{nsmap['cac']}}}TaxTotal")
        ET.SubElement(tax_total, f"{{{nsmap['cbc']}}}TaxAmount", currencyID=currency_code)
        tax_subtotal = ET.SubElement(tax_total, f"{{{nsmap['cac']}}}TaxSubtotal")
        ET.SubElement(tax_subtotal, f"{{{nsmap['cbc']}}}TaxableAmount", currencyID=currency_code)
        ET.SubElement(tax_subtotal, f"{{{nsmap['cbc']}}}TaxAmount", currencyID=currency_code)
        ET.SubElement(tax_subtotal, f"{{{nsmap['cbc']}}}CalculationSequenceNumeric")
        ET.SubElement(tax_subtotal, f"{{{nsmap['cbc']}}}Percent")
        tax_category = ET.SubElement(tax_subtotal, f"{{{nsmap['cac']}}}TaxCategory")
        tax_scheme = ET.SubElement(tax_category, f"{{{nsmap['cac']}}}TaxScheme")
        ET.SubElement(tax_scheme, f"{{{nsmap['cbc']}}}Name")
        ET.SubElement(tax_scheme, f"{{{nsmap['cbc']}}}TaxTypeCode")
        item = ET.SubElement(line_el, f"{{{nsmap['cac']}}}Item")
        ET.SubElement(item, f"{{{nsmap['cbc']}}}Description")
        ET.SubElement(item, f"{{{nsmap['cbc']}}}Name")
        price = ET.SubElement(line_el, f"{{{nsmap['cac']}}}Price")
        ET.SubElement(price, f"{{{nsmap['cbc']}}}PriceAmount", currencyID=currency_code)
        return line_el

    def _fill_invoice_line(self, node, line, index, currency, currency_code, nsmap):
        self._set_xml_text(node, 'cbc:ID', str(index), nsmap)
        # Note alanına ürün açıklamasını ekle
        note_text = line.name or (line.product_id.name if line.product_id else '')
        self._set_xml_text(node, 'cbc:Note', note_text, nsmap)

        qty_node = node.find('cbc:InvoicedQuantity', nsmap)
        if qty_node is not None:
            qty_node.text = self._float_to_str(line.quantity, digits=4)
            unit_code = self._get_line_unit_code(line)
            qty_node.set('unitCode', unit_code)

        self._set_amount_node(node, 'cbc:LineExtensionAmount', line.price_subtotal, currency, currency_code, nsmap)

        base_amount = (line.price_unit or 0.0) * (line.quantity or 0.0)
        subtotal_amount = line.price_subtotal or 0.0
        discount_amount = base_amount - subtotal_amount
        if hasattr(line, 'discount') and line.discount:
            discount_amount = max(discount_amount, base_amount * (line.discount / 100.0))
        if hasattr(line, 'discount_fixed') and line.discount_fixed:
            discount_amount = max(discount_amount, line.discount_fixed * (line.quantity or 1.0))
        if discount_amount < 0:
            discount_amount = 0.0
        for allowance_node in node.findall('cac:AllowanceCharge', nsmap):
            node.remove(allowance_node)
        if discount_amount > 0:
            allowance_node = ET.Element(f"{{{nsmap['cac']}}}AllowanceCharge")
            charge_indicator = ET.SubElement(allowance_node, f"{{{nsmap['cbc']}}}ChargeIndicator")
            charge_indicator.text = 'false'
            multiplier_node = ET.SubElement(allowance_node, f"{{{nsmap['cbc']}}}MultiplierFactorNumeric")
            discount_ratio = (discount_amount / base_amount) if base_amount else 0.0
            multiplier_node.text = self._float_to_str(discount_ratio, digits=4)
            amount_node = ET.SubElement(allowance_node, f"{{{nsmap['cbc']}}}Amount", currencyID=currency_code)
            currency_digits = currency.decimal_places if currency and currency.decimal_places is not None else 2
            amount_node.text = self._float_to_str(discount_amount, digits=currency_digits)
            base_node = ET.SubElement(allowance_node, f"{{{nsmap['cbc']}}}BaseAmount", currencyID=currency_code)
            base_node.text = self._float_to_str(base_amount, digits=currency_digits)
            line_extension = node.find('cbc:LineExtensionAmount', nsmap)
            if line_extension is not None:
                insert_index = list(node).index(line_extension) + 1
                node.insert(insert_index, allowance_node)
            else:
                node.append(allowance_node)

        tax_amount = getattr(line, 'price_tax', None)
        if tax_amount is None:
            tax_amount = line.price_total - line.price_subtotal
        tax_total_node = node.find('cac:TaxTotal', nsmap)
        if tax_total_node is not None:
            self._set_amount_node(tax_total_node, 'cbc:TaxAmount', tax_amount, currency, currency_code, nsmap)
            tax_subtotal = tax_total_node.find('cac:TaxSubtotal', nsmap)
            if tax_subtotal is not None:
                self._set_amount_node(tax_subtotal, 'cbc:TaxableAmount', line.price_subtotal, currency, currency_code, nsmap)
                self._set_amount_node(tax_subtotal, 'cbc:TaxAmount', tax_amount, currency, currency_code, nsmap)
                sequence_node = tax_subtotal.find('cbc:CalculationSequenceNumeric', nsmap)
                if sequence_node is not None:
                    sequence_node.text = str(index)
                percent_value, tax_name, tax_code = self._extract_tax_metadata(line)
                percent_node = tax_subtotal.find('cbc:Percent', nsmap)
                if percent_node is not None:
                    percent_node.text = self._float_to_str(percent_value or 0.0, digits=2)
                tax_category = tax_subtotal.find('cac:TaxCategory', nsmap)
                if tax_category is not None:
                    tax_scheme = tax_category.find('cac:TaxScheme', nsmap)
                    if tax_scheme is not None:
                        self._set_xml_text(tax_scheme, 'cbc:Name', tax_name, nsmap)
                        self._set_xml_text(tax_scheme, 'cbc:TaxTypeCode', tax_code, nsmap)

        item = node.find('cac:Item', nsmap)
        if item is not None:
            # Ürün açıklaması ve adı
            product_name = ''
            if line.product_id:
                product_name = line.product_id.name or line.product_id.display_name or ''
            
            # Description: satır açıklaması veya ürün adı
            description = line.name or product_name or 'Ürün'
            self._set_xml_text(item, 'cbc:Description', description, nsmap)
            
            # Name: ürün adı veya satır adı
            item_name = product_name or line.name or 'Ürün'
            self._set_xml_text(item, 'cbc:Name', item_name, nsmap)

        price = node.find('cac:Price', nsmap)
        if price is not None:
            self._set_amount_node(price, 'cbc:PriceAmount', line.price_unit, currency, currency_code, nsmap, price_precision=5)

    def _update_totals(self, root, currency, currency_code, invoice_lines, nsmap):
        tax_total = root.find('cac:TaxTotal', nsmap)
        if tax_total is not None:
            self._set_amount_node(tax_total, 'cbc:TaxAmount', self.amount_tax, currency, currency_code, nsmap)
            tax_subtotal = tax_total.find('cac:TaxSubtotal', nsmap)
            if tax_subtotal is not None:
                self._set_amount_node(tax_subtotal, 'cbc:TaxableAmount', self.amount_untaxed, currency, currency_code, nsmap)
                self._set_amount_node(tax_subtotal, 'cbc:TaxAmount', self.amount_tax, currency, currency_code, nsmap)
                tax_line = invoice_lines[:1]
                tax_line = tax_line[0] if tax_line else False
                percent_value, tax_name, tax_code = self._extract_tax_metadata(tax_line)
                percent_node = tax_subtotal.find('cbc:Percent', nsmap)
                if percent_node is not None:
                    percent_node.text = self._float_to_str(percent_value or 0.0, digits=2)
                tax_category = tax_subtotal.find('cac:TaxCategory', nsmap)
                if tax_category is not None:
                    tax_scheme = tax_category.find('cac:TaxScheme', nsmap)
                    if tax_scheme is not None:
                        self._set_xml_text(tax_scheme, 'cbc:Name', tax_name, nsmap)
                        self._set_xml_text(tax_scheme, 'cbc:TaxTypeCode', tax_code, nsmap)

        monetary_total = root.find('cac:LegalMonetaryTotal', nsmap)
        if monetary_total is not None:
            discount_total = 0.0
            for line in invoice_lines:
                base_amount = (line.price_unit or 0.0) * (line.quantity or 0.0)
                subtotal_amount = line.price_subtotal or 0.0
                discount_amount = base_amount - subtotal_amount
                if hasattr(line, 'discount') and line.discount:
                    discount_amount = max(discount_amount, base_amount * (line.discount / 100.0))
                if hasattr(line, 'discount_fixed') and line.discount_fixed:
                    discount_amount = max(discount_amount, line.discount_fixed * (line.quantity or 1.0))
                if discount_amount > 0:
                    discount_total += discount_amount
            self._set_amount_node(monetary_total, 'cbc:LineExtensionAmount', self.amount_untaxed, currency, currency_code, nsmap)
            self._set_amount_node(monetary_total, 'cbc:TaxExclusiveAmount', self.amount_untaxed, currency, currency_code, nsmap)
            self._set_amount_node(monetary_total, 'cbc:TaxInclusiveAmount', self.amount_total, currency, currency_code, nsmap)
            self._set_amount_node(monetary_total, 'cbc:AllowanceTotalAmount', discount_total, currency, currency_code, nsmap)
            self._set_amount_node(monetary_total, 'cbc:PayableAmount', self.amount_total, currency, currency_code, nsmap)

    def _extract_tax_metadata(self, line):
        if not line:
            return 0.0, 'KDV', '0015'
        tax = line.tax_ids[:1]
        tax = tax[0] if tax else None
        percent_value = tax.amount if tax and tax.amount_type == 'percent' else 0.0
        tax_group = tax.tax_group_id if tax else None
        tax_name = (
            getattr(tax_group, 'tax_code_name', False)
            or (tax.name if tax and tax.name else None)
            or 'KDV'
        )
        tax_code = (
            getattr(tax_group, 'tax_code', False)
            or getattr(tax, 'l10n_tr_code', False)
            or '0015'
        )
        return percent_value, tax_name, tax_code

    def _get_line_unit_code(self, line):
        if line.product_uom_id:
            return getattr(line.product_uom_id, 'l10n_tr_code', False) or 'C62'
        return 'C62'

    def _set_amount_node(self, element, xpath, amount, currency, currency_code, nsmap, price_precision=None):
        if element is None:
            return
        node = element.find(xpath, nsmap)
        if node is None:
            return
        digits = price_precision or (currency.decimal_places if currency and currency.decimal_places is not None else 2)
        amount_value = amount if amount not in (None, False) else 0.0
        if price_precision is None and currency:
            amount_value = currency.round(amount_value)
        node.text = self._float_to_str(amount_value, digits=digits)
        if currency_code:
            node.set('currencyID', currency_code)

    def _set_xml_text(self, element, xpath, value, nsmap):
        if element is None:
            return
        target = element.find(xpath, nsmap) if xpath else element
        if target is None:
            return
        if value in (None, False):
            target.text = ''
        else:
            target.text = str(value)

    def _float_to_str(self, value, digits=2):
        return f"{float(value or 0):.{digits}f}"

    def _register_xml_namespaces(self, nsmap):
        for prefix, uri in nsmap.items():
            ET.register_namespace(prefix, uri)

    def _get_amount_in_words(self, currency):
        if not currency:
            return ''
        lang = self.partner_id.lang or self.env.user.lang or 'tr_TR'
        return currency.with_context(lang=lang).amount_to_text(self.amount_total) or ''
