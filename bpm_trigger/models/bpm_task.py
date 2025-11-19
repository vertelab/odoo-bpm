from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class BPMTask(models.Model):
    _inherit = 'bpm.task'

    model_id = fields.Many2one(comodel_name='ir.model', string="Model")
    model_name = fields.Char(related='model_id.model', string='Model Name', readonly=True, store=True)
    filter_domain = fields.Char(string='Domain')
    code = fields.Html()
    trigger_type = fields.Selection([
        ('chatter', 'Chatter'),
        ('code', 'Code'),
    ], string="Trigger", default='chatter')