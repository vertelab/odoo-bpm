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

    active = fields.Boolean(string='Active', default=True)    
    description = fields.Text(string="Description")
    # task_ids = fields.Many2many(
    #     comodel_name='bpm.task',
    #     string='Tasks',
    #     help="Tasks that implement this requirement",
    #     compute='_compute_task_ids',
    #     store=True
    # )
    duration_tracking = fields.Float(string='Duration Tracking')
    bpm_id = fields.Many2one('bpm.workflow', string='BPM', ondelete='cascade', required=True)
    name = fields.Char(string="Name", required=True)
    priority = fields.Selection([
        ('must', 'Must'),
        ('should', 'Should'),
        ('could', 'Could')
    ], string="Priority", default='must')
    sequence = fields.Integer(string='Sequence')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ongoing', 'Ongoing'),
        ('done', 'Done')
    ], string="State", default='draft')
    req_type = fields.Selection([
        ('func', 'Functional'),
        ('non-func', 'Non Functional'),
    ], string="Type", default='func')
    task_ids = fields.One2many(comodel_name="bpm.requirement.task",inverse_name="req_id")

    @api.depends('bpm_id.task_ids')
    def _compute_task_ids(self):
        for requirement in self:
            Tasks = self.env['bpm.task'].search([('requirement_ids', 'in', requirement.id)])
            requirement.task_ids = [(6, 0, [f.id for f in Tasks])]


class BPMRequirementTask(models.Model):
    _name = 'bpm.requirement.task'
    _description = 'BPM Request Task'
    _order = "sequence asc"

    task_id = fields.Many2one(comodel_name='bpm.task', string="Task", help="", ondelete='cascade')
    req_id = fields.Many2one(comodel_name='bpm.requirement', string="Requirement", help="", ondelete='cascade')
    bpm_id = fields.Many2one(comodel_name='bpm.workflow', string="Workflow", help="", ondelete='cascade')
    task_type = fields.Selection(related="task_id.task_type",string='Type')
    req_type = fields.Selection(related="req_id.req_type", string="Type")
    req_state = fields.Selection(related="req_id.state", string="State")
    task_state = fields.Selection(related="task_id.state", string="State")
    sequence = fields.Integer(string='Sequence')