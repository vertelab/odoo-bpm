from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError, ValidationError
import logging

_logger = logging.getLogger(__name__)

UPDATE_FIELDS = ["name","model_id","trigger","filter_domain","filter_pre_domain","code"]


class BPMTask(models.Model):
    _inherit = 'bpm.task'

    model_id = fields.Many2one(comodel_name='ir.model', string="Model")
    model_name = fields.Char(related='model_id.model', string='Model Name', readonly=True, store=True)
    filter_pre_domain = fields.Char(string="Update before domain")
    filter_domain = fields.Char(string='Domain')
    trigger = fields.Selection([
            ('on_stage_set', "Stage is set to"),
            ('on_user_set', "User is set"),
            ('on_tag_set', "Tag is added"),
            ('on_state_set', "State is set to"),
            ('on_priority_set', "Priority is set to"),
            ('on_archive', "On archived"),
            ('on_unarchive', "On unarchived"),
            ('on_create_or_write', "On save"),
            ('on_unlink', "On deletion"),
            ('on_change', "On UI change"),
            ('on_time', "Based on date field"),
            ('on_time_created', "After creation"),
            ('on_time_updated', "After last update"),
            ("on_message_received", "On incoming message"),
            ("on_message_sent", "On outgoing message"),
            ('on_webhook', "On webhook"),
        ], string="Trigger")
    trg_selection_field_id = fields.Many2one(
        comodel_name='ir.model.fields.selection',
        string='Trigger Field',
        domain="[('field_id', 'in', trigger_field_ids)]",
        help="Some triggers need a reference to a selection field. This field is used to store it.")
    trg_field_ref = fields.Many2oneReference(
        model_field='trg_field_ref_model_name',
        string='Trigger Reference',
        help="Some triggers need a reference to another field. This field is used to store it.")
    trg_field_ref_model_name = fields.Char(string='Trigger Field Model')
    trg_date_id = fields.Many2one(
        comodel_name='ir.model.fields', 
        string='Trigger Date',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('date', 'datetime'))]",
        help="""When should the condition be triggered.
                If present, will be checked by the scheduler. If empty, will be checked at creation and update.""")
    code = fields.Html()
    automation_id = fields.Many2one(comodel_name="base.automation")
    action_server_ids = fields.One2many(comodel_name="ir.actions.server", inverse_name="base_automation_id",
        context={'default_usage': 'base_automation'},
        string="Actions",
        compute="_compute_action_server_ids",
        store=True,
        readonly=False,
    )

    @api.onchange("model_id","trigger")
    def _create_automation(self):
        if self.model_id and self.trigger != False and not self.automation_id:
            automation_id = self.env["base.automation"].create({
                "name": f"{self.bpm_id.name} - {self.name}",
                "model_id": self.model_id.id,
                "trigger": self.trigger
            })
            self.automation_id = automation_id.id

    def write(self,vals):
        res = super(BPMTask,self).write(vals)
        if self.automation_id:
            update_vals = {}
            for key in UPDATE_FIELDS:
                if key in vals.keys():
                    value = getattr(self,key,False)
                    if value:
                        update_vals.update({key:value})
            self.automation_id.write(update_vals)
        return res

    @api.depends('model_id')
    def _compute_action_server_ids(self):
        """ When changing / setting model, remove actions that are not targeting
        the same model anymore. """
        for rule in self.filtered('model_id'):
            actions_to_remove = rule.action_server_ids.filtered(
                lambda action: action.model_id != rule.model_id
            )
            if actions_to_remove:
                rule.action_server_ids = [(3, action.id) for action in actions_to_remove]

   