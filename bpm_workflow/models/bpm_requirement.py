from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
import re
import html
from bs4 import BeautifulSoup

import logging

_logger = logging.getLogger(__name__)

class BPMRequirement(models.Model):
    _name = 'bpm.requirement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BPM Requirement'
    _order = "sequence desc"

    description = fields.Text(string="Description")
    task_ids = fields.Many2many(
        comodel_name='bpm.task',
        string='Tasks',
        help="Tasks that implement this requirement",
        compute='_compute_task_ids',
        store=True
    )
    bpm_id = fields.Many2one('bpm.workflow', string='BPM', ondelete='cascade', required=True)
    name = fields.Char(string="Name", required=True)
    priority = fields.Selection([
        ('must', 'Must'),
        ('should', 'Should'),
        ('could', 'Could')
    ], string="Priority", default='must')
    sequence = fields.Integer(string='Sequence')
    req_type = fields.Selection([
        ('func', 'Funtional'),
        ('non-func', 'Non Functional'),
    ], string="Type", default='func')

    @api.depends('bpm_id.task_ids')
    def _compute_task_ids(self):
        for requirement in self:
            Tasks = self.env['bpm.task'].search([('requirement_ids', 'in', requirement.id)])
            requirement.task_ids = [(6, 0, [f.id for f in Tasks])]
