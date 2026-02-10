{
    'name': 'E Fatura',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'E-Devlet Ürünleri',
    'description': """
E-Devlet Management
=====================
This module allows you to create and manage E-Devlet records from Sale Orders.

Features:
---------
* Track status
    """,
    'author': 'Emre Yılmaz',
    'website': 'https://www.pbsyazilim.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'stock',
        'mail',
        'account',
    ],
    'data': [
        'views/integration_view.xml',
        'views/einvoice_views.xml',
        'views/account_move_views.xml',
        'views/invoice_xml_preview_wizard_views.xml',
        'views/account_tax_group_views.xml',
        'views/res_partner_views.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
