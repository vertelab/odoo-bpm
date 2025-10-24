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

    duration_tracking = fields.Float(string='Duration Tracking')
    active = fields.Boolean(string='Active', default=True)
    parent_id = fields.Many2one(comodel_name='bpm.workflow',string="Parent BPM",help="")
    company_id = fields.Many2one(comodel_name='res.company',string="Company",help="") 
    name = fields.Char(string="Titel", required=True)
    description = fields.Text(string="Description",help="Purpuse")
    version = fields.Char(string="Version", default="1.0",readonly=True,tracking=True)
    author_id = fields.Many2one('res.users', string="Author",tracking=True)
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

    tasks_count = fields.Integer(string="Total Tasks", compute='_compute_Tasks_counts')
    closed_tasks_count = fields.Integer(string="Closed Tasks", compute='_compute_Tasks_counts')
    tasks_percentage = fields.Float(string="Tasks Completion %", compute='_compute_Tasks_counts')
    
    
    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'approved':
            self.approved_by_id = self.env.user.id
            self.date = fields.Date.today()
        else:
            self.approved_by_id = False

    @api.depends('task_ids')
    def _compute_Tasks_counts(self):
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

    def action_Tasks(self):
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



class BPMTask(models.Model):
    _name = 'bpm.task'
    _inherit = ['mermaid.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'BPM Task'
    _order = "sequence desc"

    parent_id = fields.Many2one(comodel_name='bpm.task',string="Parent Task",help="") 
    description = fields.Text(string="Description")
    duration_tracking = fields.Float(string='Duration Tracking')
    image_128 = fields.Image("Image", max_width=128, max_height=128)
    name = fields.Char(string="Name", required=True)
    process_data = fields.Text(string="Process")
    bpm_id = fields.Many2one('bpm.workflow', string='BPM', ondelete='cascade', required=True)
    requirement_ids = fields.One2many(comodel_name='bpm.requirement.task', inverse_name='task_id')
    requirement_names_ids = fields.Many2many(comodel_name='bpm.requirement',string="Requirement",compute='_compute_requirement_names_ids') 
    @api.depends('requirement_ids.task_id')
    def _compute_requirement_names_ids(self):
        for record in self:
            record.requirement_names_ids = record.requirement_ids.mapped('req_id')

    
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

class BPMRequirementTask(models.Model):
    _name = 'bpm.requirement.task'
    _description = 'BPM Request Task'
    _order = "sequence asc"

    task_id = fields.Many2one(comodel_name='bpm.task', string="Task", help="", ondelete='cascade')
    req_id = fields.Many2one(comodel_name='bpm.requirement', string="", help="", ondelete='cascade')
    prd_id = fields.Many2one(comodel_name='bpm.document', string="", help="", ondelete='cascade')
    task_type = fields.Selection(related="task_id.task_type",string='Taks Type')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ongoing', 'Ongoing'),
        ('done', 'Done')
    ], string="State", default='draft')    
    sequence = fields.Integer(string='Sequence')


class BPMRequirement(models.Model):
    _name = 'bpm.requirement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BPM Requirement'
    _order = "sequence desc"

    description = fields.Text(string="Description")
    duration_tracking = fields.Float(string='Duration Tracking')

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
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ongoing', 'Ongoing'),
        ('done', 'Done')
    ], string="State", default='draft')
    req_type = fields.Selection([
        ('func', 'Funtional'),
        ('non-func', 'Non Functional'),
    ], string="Type", default='func')

    @api.depends('bpm_id.task_ids')
    def _compute_task_ids(self):
        for requirement in self:
            Tasks = self.env['bpm.task'].search([('requirement_ids', 'in', requirement.id)])
            requirement.task_ids = [(6, 0, [f.id for f in Tasks])]
