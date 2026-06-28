# -*- coding: utf-8 -*-
{
    'name': 'BPM: Law Packages',
    'version': '1.0',
    'summary': 'Pre-configured law packages for different business types.',
    'category': 'Management',
    'description': """
Law Packages for Business Types
===============================

Provides pre-configured packages of relevant Swedish laws (SFS) for
different business types. Users select their business type(s) in
Settings and the corresponding laws are loaded into the management
system's law monitoring module.

Business types included:
- Consulting Firm (Konsultbyrå)
- Manufacturing Company (Tillverkande företag)
- Restaurant (Restaurang)

Features:
- Select one or multiple business type packages in Settings
- Laws are automatically linked to document.law records
- Each law includes SFS number, name, category, and relevance note
- Integration with mgmtsystem_law for management system tracking
    """,
    'author': 'Vertel AB',
    'website': 'https://vertel.se',
    'license': 'AGPL-3',
    'depends': [
        'mgmtsystem_law',
        'document_law',
        'bpm_workflow',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/law_package_consulting.xml',
        'data/law_package_manufacturing.xml',
        'data/law_package_restaurant.xml',
        'data/law_package_law_firm.xml',
        'data/law_package_retail.xml',
        'data/law_package_webshop.xml',
        'views/law_package_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
