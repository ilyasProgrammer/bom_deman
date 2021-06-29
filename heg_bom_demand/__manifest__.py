# -*- coding: utf-8 -*-

{
    "name": """HEG BOM Demand""",
    "summary": """HEG BOM Demand""",
    "category": "Manufacturing",
    "version": "13.0.0.1",
    "author": "Ilyas",
    "support": "http://gitgmbh.com",
    "website": "http://gitgmbh.com",
    "license": "Other proprietary",
    "depends": [
        'sale_management',
        'mrp',
    ],
    "data": [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'report/bom_demand.xml',
    ],
    "qweb": [
    ],
    "application": False,
    "pre_init_hook": None,
    "post_init_hook": None,
    "auto_install": False,
    "installable": True,
}
