from datetime import datetime, timedelta 
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
import re
import html
from bs4 import BeautifulSoup

import logging

_logger = logging.getLogger(__name__)


from odoo import models, fields


class BPMWorkflow(models.Model):
    _name = 'bpm.workflow'
    _inherit = ['mermaid.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'BPM Workflow'

    author_id = fields.Many2one('res.users', string="Author",tracking=True)
    active = fields.Boolean(string='Active', default=True)
    duration_tracking = fields.Float(string='Duration Tracking')
    parent_id = fields.Many2one(comodel_name='bpm.workflow',string="Parent BPM",help="")
    company_id = fields.Many2one(comodel_name='res.company',string="Company",help="") 
    name = fields.Char(string="Titel", required=True)
    description = fields.Text(string="Description",help="Purpuse")
    image_128 = fields.Image("Image", max_width=128, max_height=128, compute='_compute_image_128')
    version = fields.Char(string="Version", default="1.0",readonly=True,tracking=True)
    process_owner_id = fields.Many2one('res.users', string="Process Owner",tracking=True)
    approved_by_id = fields.Many2one('res.users', string="Approved By",readonly=True,tracking=True)
    date = fields.Date(string="Date", default=fields.Date.today,readonly=True,tracking=True)
    goals = fields.Text(string="Goal")
    success_criteria = fields.Text(string="Success Criteria")
    dependencies = fields.Text(string="Dependencies")
    risks = fields.Text(string="Risks")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('deprecated', 'Deprecated')],
        string="State",
        default='draft',
        tracking=True
    )
    requirement_ids = fields.One2many(comodel_name='bpm.requirement',inverse_name='bpm_id',string="Requirements",help="") 
    task_ids = fields.One2many(comodel_name='bpm.task',inverse_name='bpm_id',string="Tasks",help="") 

    requirements_count = fields.Integer(string="Total Requirements", compute='_compute_requirements_counts')
    closed_requirements_count = fields.Integer(string="Closed Requirements", compute='_compute_requirements_counts')
    requirements_percentage = fields.Float(string="Requirements Completion %", compute='_compute_requirements_counts')

    tasks_count = fields.Integer(string="Total Tasks", compute='_compute_tasks_counts')
    closed_tasks_count = fields.Integer(string="Closed Tasks", compute='_compute_tasks_counts')
    tasks_percentage = fields.Float(string="Tasks Completion %", compute='_compute_tasks_counts')
    
    
    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'approved':
            self.approved_by_id = self.env.user.id
            self.date = fields.Date.today()
        else:
            self.approved_by_id = False

    @api.depends('task_ids')
    def _compute_tasks_counts(self):
        for record in self:
            total = len(record.task_ids)
            closed = len(record.task_ids.filtered(lambda f: f.state == 'done'))
            record.tasks_count = total
            record.closed_tasks_count = closed
            record.tasks_percentage = (closed / total * 100) if total else 0.0

    @api.depends('requirement_ids')
    def _compute_requirements_counts(self):
        for record in self:
            total = len(record.requirement_ids)
            closed = len(record.requirement_ids.filtered(lambda r: r.state == 'done'))  
            record.requirements_count = total
            record.closed_requirements_count = closed
            record.requirements_percentage = 0.0
            if total > 0:
                record.requirements_percentage = (closed / total) * 100


    def button_minor_version(self):
        for record in self:
            major, minor = record.version.split('.')
            # Increment minor
            minor = str(int(minor) + 1)
            record.version = f"{major}.{minor}"
            record.date = fields.Date.today()

    def button_major_version(self):
        for record in self:
            major, minor = record.version.split('.')
            # Increment major and reset minor to 0
            major = str(int(major) + 1)
            record.version = f"{major}.0"
            record.date = fields.Date.today()

    def action_tasks(self):
      return {
          'type': 'ir.actions.act_window',
          'name': 'Tasks',
          'res_model': 'bpm.task',
          'domain': [('bpm_id', '=', self.id)],
          'view_mode': 'kanban,list,form',
          'context': {'default_bpm_id': self.id},
          'target': 'current',
      }

    def action_requirements(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Requirements',
            'res_model': 'bpm.requirement',
            'domain': [('bpm_id', '=', self.id)],
            'view_mode': 'list,form',
            'context': {'default_bpm_id': self.id},
            'target': 'current',
        }

