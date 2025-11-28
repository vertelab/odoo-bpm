import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError

_logger = logging.getLogger(__name__)

class BPMTaskDecision(models.Model):
    _name = 'bpm.task.decision'
    _description = 'BPM task glue model for children and parents'
    _order = "sequence desc"

    bpm_id = fields.Many2one(comodel_name="bpm.workflow")
    parent_id = fields.Many2one(comodel_name="bpm.task", domain="[('task_type','!=','end'),('bpm_id', '=', bpm_id)]")
    child_id = fields.Many2one(comodel_name="bpm.task",domain="[('task_type','!=','start'),('bpm_id', '=', bpm_id)]")
    sequence = fields.Integer(string='Sequence')
    option = fields.Char()
