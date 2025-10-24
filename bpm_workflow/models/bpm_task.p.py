import logging
import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools.misc import file_path

_logger = logging.getLogger(__name__)

class BPMTask(models.Model):
    _name = 'bpm.task'
    _inherit = ['mermaid.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'BPM Task'
    _order = "sequence desc"

    active = fields.Boolean(string='Active', default=True)
    bpm_id = fields.Many2one('bpm.workflow', string='BPM', ondelete='cascade', required=True)
    parent_id = fields.Many2one(comodel_name='bpm.task',string="Parent Task",help="")
    child_ids = fields.One2many(comodel_name="bpm.task",inverse_name="parent_id")
    description = fields.Text(string="Description")
    duration_tracking = fields.Float(string='Duration Tracking')
    image_128 = fields.Image("Image", max_width=128, max_height=128, compute='_compute_image_128')
    name = fields.Char(string="Name", required=True)
    process_data = fields.Text(string="Process")
    requirement_ids = fields.One2many(comodel_name='bpm.requirement.task', inverse_name='task_id')
    requirement_names_ids = fields.Many2many(comodel_name='bpm.requirement', string="Requirement",
                                             compute='_compute_requirement_names_ids')
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
    trigger_type = fields.Selection([
        ('chatter', 'Chatter'),
        ('code', 'Code'),
    ], string="Trigger", default='chatter')
    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    model_id = fields.Many2one(comodel_name='ir.model', string="Model")
    model_name = fields.Char(related='model_id.model', string='Model Name', readonly=True, store=True)
    filter_domain = fields.Char(string='Domain')

    @api.depends('requirement_ids.task_id')
    def _compute_requirement_names_ids(self):
        for record in self:
            record.requirement_names_ids = record.requirement_ids.mapped('req_id')

    @api.depends('task_type')
    def _compute_image_128(self):
        """Set image based on task type"""
        for record in self:
            if not record.task_type:
                record.image_128 = False
                continue

            # Map task types to image filenames
            image_map = {
                'task': 'task.png',
                'end': 'end.png',
                'start': 'startpoint.png',
                'decision': 'decision.png',
            }

            filename = image_map.get(record.task_type)
            if not filename:
                record.image_128 = False
                continue

            # Get the image path from the module
            image_path = file_path(f"bpm_workflow/static/img/{filename}")

            if image_path:
                with open(image_path, 'rb') as f:
                    record.image_128 = base64.b64encode(f.read())
            else:
                record.image_128 = False