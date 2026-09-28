# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo SA, Open Source Management Solution, third party addon
#    Copyright (C) 2025- Vertel AB (<https://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'BPM: Workflow Engine',
    'version': '1.0',
    'summary': 'A Product Requirements Document (PRD) is a formal document that outlines the purpose, features, and requirements.',
    'category': 'Productivity',
    'description': """
        A BPM Workflow Engine is specialized software designed to manage and automate business processes systematically and efficiently. It controls the sequence of tasks within a defined business process, ensuring that each step is executed by the appropriate person or system at the right time according to preset rules, events, and conditions. The engine can route tasks, make decisions based on conditions, trigger actions, and integrate with other software systems via APIs to enable seamless data exchange and task automation.

This software uses process definitions often modeled with standards like BPMN (Business Process Model and Notation) to visually represent workflows and specify task sequences, decision points, and timelines. It reduces manual work, minimizes errors, and speeds up process execution by automating routine and complex tasks. Additionally, it provides real-time monitoring, logging, and notifications so process managers can track progress and intervene if needed.

In a BPM context, a workflow engine is the technical core that orchestrates how business operations flow in an automated, transparent, and auditable manner, supporting efficiency and process compliance. It allows organizations to flexibly configure workflows, assign roles, enforce business rules, and adjust processes dynamically without heavy coding requirements, often through drag-and-drop interfaces or process definition languages. This approach helps align IT and business users in managing process improvements and ensures scalable, adaptable business process automation

    """,
    'author': 'Vertel AB',
    'website': 'https://vertel.se/apps/odoo-bpm/bpm_workflow',
    'license': 'AGPL-3',
    'contributor': '',
    'maintainer': 'Vertel AB',
    'depends': [
        'mail',
        'web_mermaid_ai'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/bpm_security.xml',
        'views/bpm_workflow_views.xml',
        'views/bpm_task_views.xml',
        'views/bpm_requirement_views.xml',
        'views/bpm_instance_views.xml',
        'wizard/bpmn_import_views.xml',
    ],
    'application': True,
}
