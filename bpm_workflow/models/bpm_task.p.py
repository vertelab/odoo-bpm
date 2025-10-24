from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
import re
import html
from bs4 import BeautifulSoup

import logging

_logger = logging.getLogger(__name__)

class BPMTask(models.Model):
    _name = 'bpm.task'
    _inherit = ['mermaid.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'BPM Task'
    _order = "sequence desc"

    parent_id = fields.Many2one(comodel_name='bpm.task',string="Parent Task",help="")
    description = fields.Text(string="Description")
    name = fields.Char(string="Name", required=True)
    process_data = fields.Text(string="Process")
    priority = fields.Selection([
        ('must', 'Must'),
        ('should', 'Should'),
        ('could', 'Could')
    ], string="Priority", default='must')
    bpm_id = fields.Many2one('bpm.workflow', string='BPM', ondelete='cascade', required=True)
    prompt = fields.Text(string="Prompt")
    requirement_ids = fields.One2many(
        comodel_name='bpm.requirement',
        inverse_name='bpm_id',
        string="Requirements",
        help=""
    )
    action = fields.Text(string='Action')
    menu = fields.Text(string='Menu')
    sequence = fields.Integer(string='Sequence')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ongoing', 'Ongoing'),
        ('done', 'Done')
    ], string="State", default='draft')
    task_type = fields.Selection([
        ('task', 'Task'),
        ('end', 'Endpoint'),
        ('start', 'Startpoint'),
        ('decision', 'Decision'),
    ], string="Type", default='task')
    decision_type = fields.Selection([
        ('man', 'Manual'),
        ('domain', 'Conditions'),
    ], string="Decision", default='man')
    user_id = fields.Many2one(comodel_name='res.users',string="Author",help="")
    image_128 = fields.Image("Image", max_width=128, max_height=128)
    trigger_type = fields.Selection([
        ('chatter', 'Chatter'),
        ('code', 'Code'),
    ], string="Trigger", default='chatter')

    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)

    model_id = fields.Many2one(comodel_name='ir.model', string="Model")
    model_name = fields.Char(related='model_id.model', string='Model Name', readonly=True, store=True)
    filter_domain = fields.Char(string='Domain')
