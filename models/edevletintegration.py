from datetime import date
import logging
from urllib import request
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET

from odoo import models, fields, api, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

SOAP_ENV_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
TEMPURI_NS = 'http://tempuri.org/'

class EdevletIntegration(models.Model):
    _name = 'edevlet.integration'
    _description = 'E-Invoice Integration Configuration'
    
    type = fields.Selection([
        ('1', 'EFATURA'),
        ('2', 'EARSIV'),
        ('3', 'EIRSALIYE')
    ], string='Type', required=True)
    company_code = fields.Integer(string='Company Code', required=True)
    api_user_name = fields.Char(string='API User Name', size=100, required=True)
    api_password = fields.Char(string='API Password', size=100, required=True)
    web_service_url = fields.Char(string='Web Service URL', size=255)
    prefix = fields.Char(string='Prefix', size=5)
    ubl_version = fields.Char(string='UBL Version', size=5)
    customization_id = fields.Char(string='Customization ID', size=10)
    template_file_name = fields.Char(string='Template File Name', size=50)
    sirket_kodu = fields.Char(string='Şirket Kodu', size=10)
    xslt_file = fields.Binary(string='XSLT File', attachment=True)
    xslt_file_name = fields.Char(string='XSLT File Name', size=128)
    xslt_base64 = fields.Text(
        string='XSLT Base64',
        compute='_compute_xslt_base64',
        store=True,
        readonly=True,
        help='Uploaded XSLT file encoded as base64.',
    )

    @api.depends('xslt_file')
    def _compute_xslt_base64(self):
        for record in self:
            xslt_file = record.with_context(bin_size=False).xslt_file
            record.xslt_base64 = xslt_file or False

    def action_import_taxpayer_list(self):
        self.ensure_one()
        start_date = date(date.today().year - 1, 1, 1).strftime('%Y-%m-%d')
        imported_count = self._import_taxpayer_list(start_date=start_date)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('İşlem Başarılı'),
                'message': _('%s adet mükellef kaydı içe aktarıldı/güncellendi.') % imported_count,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_import_all_taxpayer_list(self):
        self.ensure_one()
        imported_count = self._import_taxpayer_list(start_date='2010-01-01')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('İşlem Başarılı'),
                'message': _('%s adet mükellef kaydı içe aktarıldı/güncellendi.') % imported_count,
                'type': 'success',
                'sticky': False,
            },
        }

    def _import_taxpayer_list(self, start_date):
        self.ensure_one()
        if not self.web_service_url:
            raise UserError(_('Web Service URL alanı zorunludur.'))
        if not self.sirket_kodu or not self.api_user_name or not self.api_password:
            raise UserError(_('Şirket Kodu, API Kullanıcı Adı ve API Şifre alanları zorunludur.'))

        ticket = self._get_forms_authentication_ticket()
        return self._stream_and_upsert_taxpayers(ticket=ticket, start_date=start_date)

    def _get_forms_authentication_ticket(self):
        envelope = f'''<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:tem="{TEMPURI_NS}">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:GetFormsAuthenticationTicket>
         <tem:CorporateCode>{self.sirket_kodu}</tem:CorporateCode>
         <tem:LoginName>{self.api_user_name}</tem:LoginName>
         <tem:Password><![CDATA[{self.api_password}]]></tem:Password>
      </tem:GetFormsAuthenticationTicket>
   </soapenv:Body>
</soapenv:Envelope>'''
        response_text = self._send_soap_request(
            envelope=envelope,
            soap_action='http://tempuri.org/GetFormsAuthenticationTicket',
        )
        root = self._parse_xml(response_text)
        ns = {'soap': SOAP_ENV_NS, 'tem': TEMPURI_NS}
        ticket_node = root.find('.//tem:GetFormsAuthenticationTicketResult', ns)
        if ticket_node is None or not ticket_node.text:
            raise UserError(_('Ticket bilgisi SOAP cevabında bulunamadı.'))
        return ticket_node.text.strip()

    def _get_taxpayer_nodes(self, ticket, start_date):
        envelope = f'''<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:tem="{TEMPURI_NS}">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:GetTaxIdListbyDate>
         <tem:Ticket>{ticket}</tem:Ticket>
         <tem:StartDate>{start_date}</tem:StartDate>
      </tem:GetTaxIdListbyDate>
   </soapenv:Body>
</soapenv:Envelope>'''
        response_text = self._send_soap_request(
            envelope=envelope,
            soap_action='http://tempuri.org/GetTaxIdListbyDate',
        )
        root = self._parse_xml(response_text)
        ns = {'tem': TEMPURI_NS}
        service_result = root.findtext('.//tem:ServiceResult', default='', namespaces=ns)
        if service_result and service_result.lower() != 'successful':
            description = root.findtext('.//tem:ServiceResultDescription', default='', namespaces=ns)
            error_code = root.findtext('.//tem:ErrorCode', default='', namespaces=ns)
            raise UserError(
                _('Mükellef sorgusu başarısız oldu. Hata Kodu: %(code)s Açıklama: %(desc)s')
                % {'code': error_code or '-', 'desc': description or '-'}
            )
        return root.findall('.//tem:EInvoiceCustomerResult', ns)

    def _stream_and_upsert_taxpayers(self, ticket, start_date):
        envelope = f'''<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:tem="{TEMPURI_NS}">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:GetTaxIdListbyDate>
         <tem:Ticket>{ticket}</tem:Ticket>
         <tem:StartDate>{start_date}</tem:StartDate>
      </tem:GetTaxIdListbyDate>
   </soapenv:Body>
</soapenv:Envelope>'''
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://tempuri.org/GetTaxIdListbyDate',
        }
        req = request.Request(
            self.web_service_url,
            data=envelope.encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            with request.urlopen(req, timeout=300) as response:
                return self._upsert_taxpayers_from_xml_stream(response)
        except HTTPError as error:
            error_body = error.read(20000).decode('utf-8', errors='ignore') if hasattr(error, 'read') else ''
            _logger.exception('SOAP HTTP error while requesting %s', 'http://tempuri.org/GetTaxIdListbyDate')
            raise UserError(_('SOAP HTTP hatası: %(status)s\n%(body)s') % {
                'status': error.code,
                'body': error_body,
            }) from error
        except URLError as error:
            _logger.exception('SOAP connection error while requesting %s', 'http://tempuri.org/GetTaxIdListbyDate')
            raise UserError(_('SOAP bağlantı hatası: %s') % error.reason) from error

    def _upsert_taxpayers_from_xml_stream(self, xml_stream):
        company_import_model = self.env['einvoice.company.import']
        imported_count = 0
        einvoice_type = int(self.type) if self.type and str(self.type).isdigit() else False

        service_result = ''
        service_result_description = ''
        error_code = ''

        try:
            context = ET.iterparse(xml_stream, events=('start', 'end'))
            _, root = next(context)
        except ET.ParseError as error:
            _logger.exception('SOAP response parse error')
            raise UserError(_('SOAP cevabı parse edilemedi.')) from error

        for event, elem in context:
            if event != 'end':
                continue

            if elem.tag == f'{{{TEMPURI_NS}}}ServiceResult':
                service_result = (elem.text or '').strip()
            elif elem.tag == f'{{{TEMPURI_NS}}}ServiceResultDescription':
                service_result_description = (elem.text or '').strip()
            elif elem.tag == f'{{{TEMPURI_NS}}}ErrorCode':
                error_code = (elem.text or '').strip()
            elif elem.tag == f'{{{TEMPURI_NS}}}EInvoiceCustomerResult':
                tax_no = (elem.findtext(f'{{{TEMPURI_NS}}}TaxIdOrPersonalId') or '').strip()
                alias = (elem.findtext(f'{{{TEMPURI_NS}}}Alias') or '').strip()
                if tax_no:
                    values = {
                        'tax_no': tax_no,
                        'alias': alias,
                        'type': self._normalize_node_text(elem.findtext(f'{{{TEMPURI_NS}}}Type')),
                        'company_fullname': self._normalize_node_text(elem.findtext(f'{{{TEMPURI_NS}}}Name')),
                        'register_date': self._normalize_datetime(self._normalize_node_text(elem.findtext(f'{{{TEMPURI_NS}}}RegisterTime'))),
                        'alias_creation_date': self._normalize_datetime(self._normalize_node_text(elem.findtext(f'{{{TEMPURI_NS}}}AliasCreateDate'))),
                        'einvoice_type': einvoice_type,
                    }
                    domain = [('tax_no', '=', tax_no)]
                    if alias:
                        domain.append(('alias', '=', alias))
                    existing_record = company_import_model.search(domain, limit=1)
                    if existing_record:
                        existing_record.write(values)
                    else:
                        company_import_model.create(values)
                    imported_count += 1
                elem.clear()
                root.clear()

        if service_result and service_result.lower() != 'successful':
            raise UserError(
                _('Mükellef sorgusu başarısız oldu. Hata Kodu: %(code)s Açıklama: %(desc)s')
                % {'code': error_code or '-', 'desc': service_result_description or '-'}
            )

        return imported_count

    def _check_customer_tax_id(self, ticket, tax_id_or_personal_id):
        envelope = f'''<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:tem="{TEMPURI_NS}">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:CheckCustomerTaxId>
         <tem:Ticket>{ticket}</tem:Ticket>
         <tem:TaxIdOrPersonalId>{tax_id_or_personal_id}</tem:TaxIdOrPersonalId>
      </tem:CheckCustomerTaxId>
   </soapenv:Body>
</soapenv:Envelope>'''
        response_text = self._send_soap_request(
            envelope=envelope,
            soap_action='http://tempuri.org/CheckCustomerTaxId',
        )
        root = self._parse_xml(response_text)
        ns = {'tem': TEMPURI_NS}

        service_result = root.findtext('.//tem:ServiceResult', default='', namespaces=ns)
        service_description = root.findtext('.//tem:ServiceResultDescription', default='', namespaces=ns)
        error_code = root.findtext('.//tem:ErrorCode', default='', namespaces=ns)
        if service_result and service_result.lower() != 'successful':
            raise UserError(
                _('Mükelleflik kontrolü başarısız oldu. Hata Kodu: %(code)s Açıklama: %(desc)s')
                % {'code': error_code or '-', 'desc': service_description or '-'}
            )

        customers = root.findall('.//tem:EInvoiceCustomerResult', ns)
        if not customers:
            return _('Sorgu başarılı fakat kayıt bulunamadı.')

        self._upsert_check_customer_tax_id_results(customers)

        lines = []
        for customer in customers:
            is_exist = (customer.findtext(f'{{{TEMPURI_NS}}}IsExist') or '').strip().lower()
            lines.append(
                _('%(tax_id)s | %(name)s | %(alias)s | Durum: %(status)s') % {
                    'tax_id': self._normalize_node_text(customer.findtext(f'{{{TEMPURI_NS}}}TaxIdOrPersonalId')) or '-',
                    'name': self._normalize_node_text(customer.findtext(f'{{{TEMPURI_NS}}}Name')) or '-',
                    'alias': self._normalize_node_text(customer.findtext(f'{{{TEMPURI_NS}}}Alias')) or '-',
                    'status': _('Var') if is_exist == 'true' else _('Yok'),
                }
            )

        return '\n'.join(lines)

    def _upsert_check_customer_tax_id_results(self, customer_nodes):
        company_import_model = self.env['einvoice.company.import']
        einvoice_type = int(self.type) if self.type and str(self.type).isdigit() else False

        for node in customer_nodes:
            tax_no = self._normalize_node_text(node.findtext(f'{{{TEMPURI_NS}}}TaxIdOrPersonalId'))
            alias = self._normalize_node_text(node.findtext(f'{{{TEMPURI_NS}}}Alias'))
            if not tax_no:
                continue

            values = {
                'tax_no': tax_no,
                'alias': alias,
                'type': self._normalize_node_text(node.findtext(f'{{{TEMPURI_NS}}}Type')),
                'company_fullname': self._normalize_node_text(node.findtext(f'{{{TEMPURI_NS}}}Name')),
                'register_date': self._normalize_datetime(self._normalize_node_text(node.findtext(f'{{{TEMPURI_NS}}}RegisterTime'))),
                'alias_creation_date': self._normalize_datetime(self._normalize_node_text(node.findtext(f'{{{TEMPURI_NS}}}AliasCreateDate'))),
                'einvoice_type': einvoice_type,
            }
            domain = [('tax_no', '=', tax_no)]
            if alias:
                domain.append(('alias', '=', alias))
            existing_record = company_import_model.search(domain, limit=1)
            if existing_record:
                existing_record.write(values)
            else:
                company_import_model.create(values)

    def _upsert_taxpayers(self, customer_nodes):
        company_import_model = self.env['einvoice.company.import']
        imported_count = 0
        einvoice_type = int(self.type) if self.type and str(self.type).isdigit() else False
        for node in customer_nodes:
            tax_no = self._get_node_text(node, 'TaxIdOrPersonalId')
            alias = self._get_node_text(node, 'Alias')
            if not tax_no:
                continue
            values = {
                'tax_no': tax_no,
                'alias': alias,
                'type': self._get_node_text(node, 'Type'),
                'company_fullname': self._get_node_text(node, 'Name'),
                'register_date': self._normalize_datetime(self._get_node_text(node, 'RegisterTime')),
                'alias_creation_date': self._normalize_datetime(self._get_node_text(node, 'AliasCreateDate')),
                'einvoice_type': einvoice_type,
            }
            domain = [('tax_no', '=', tax_no)]
            if alias:
                domain.append(('alias', '=', alias))
            existing_record = company_import_model.search(domain, limit=1)
            if existing_record:
                existing_record.write(values)
            else:
                company_import_model.create(values)
            imported_count += 1
        return imported_count

    def _send_soap_request(self, envelope, soap_action):
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': soap_action,
        }
        req = request.Request(
            self.web_service_url,
            data=envelope.encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            with request.urlopen(req, timeout=60) as response:
                return response.read().decode('utf-8', errors='ignore')
        except HTTPError as error:
            error_body = error.read().decode('utf-8', errors='ignore') if hasattr(error, 'read') else ''
            _logger.exception('SOAP HTTP error while requesting %s', soap_action)
            raise UserError(_('SOAP HTTP hatası: %(status)s\n%(body)s') % {
                'status': error.code,
                'body': error_body,
            }) from error
        except URLError as error:
            _logger.exception('SOAP connection error while requesting %s', soap_action)
            raise UserError(_('SOAP bağlantı hatası: %s') % error.reason) from error

    def _parse_xml(self, payload):
        try:
            return ET.fromstring(payload)
        except ET.ParseError as error:
            _logger.exception('SOAP response parse error')
            raise UserError(_('SOAP cevabı parse edilemedi.')) from error

    def _get_node_text(self, parent_node, tag_name):
        node = parent_node.find(f'{{{TEMPURI_NS}}}{tag_name}')
        if node is None or not node.text:
            return False
        return node.text.strip()

    def _normalize_datetime(self, value):
        if not value:
            return False
        return value.replace('T', ' ').replace('Z', '')

    def _normalize_node_text(self, value):
        if not value:
            return False
        cleaned_value = value.strip()
        return cleaned_value or False
