import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError, ValidationError
import logging

_logger = logging.getLogger(__name__)

# Regex for extracting field names from domain strings (matches Odoo's base.automation)
DOMAIN_FIELDS_RE = re.compile(r'(?:["\'](\w+)["\'])')

UPDATE_FIELDS = {"name", "model_id", "trigger", "filter_domain", "filter_pre_domain", "code"}


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
    trigger_field_ids = fields.Many2many(
        comodel_name='ir.model.fields',
        compute='_compute_trigger_field_ids',
        store=False,
    )
    action_server_ids = fields.One2many(comodel_name="ir.actions.server", inverse_name="base_automation_id",
        context={'default_usage': 'base_automation'},
        string="Actions",
        compute="_compute_action_server_ids",
        store=True,
        readonly=False,
    )

    @api.depends('model_id', 'trigger', 'filter_domain')
    def _compute_trigger_field_ids(self):
        for automation in self:
            if automation.trigger == "on_create_or_write":
                automation.trigger_field_ids |= automation._get_filter_domain_fields()
                continue
            automation._onchange_trigger()

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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._sync_automation()
        return records

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            record._sync_automation(vals)
        return res

    def _sync_automation(self, vals=None):
        """Sync BPM task configuration with underlying base.automation record.
        Creates or updates the automation record to match the trigger settings."""
        if not self.model_id or self.trigger in (False, None):
            return

        if not self.automation_id:
            # Create new automation
            automation = self.env["base.automation"].create({
                "name": f"{self.bpm_id.name} - {self.name}",
                "model_id": self.model_id.id,
                "trigger": self.trigger,
            })
            # Use SQL write to avoid recursion
            self.env.cr.execute(
                "UPDATE bpm_task SET automation_id = %s WHERE id = %s",
                (automation.id, self.id)
            )
            self.invalidate_recordset(['automation_id'])
        elif vals:
            # Update existing automation with changed fields
            update_vals = {}
            for key in UPDATE_FIELDS:
                if key in vals:
                    value = vals[key]
                    if value:
                        update_vals[key] = value
            if update_vals:
                self.automation_id.write(update_vals)

    def _get_filter_domain_fields(self):
        self.ensure_one()
        if not self.filter_domain or not self.model_id:
            return self.env['ir.model.fields']
        model = self.model_id.model
        fields = self.env["ir.model.fields"]
        # wondering why we use a regex instead of safe_eval?
        # because this method is called on a compute method hence could be triggered
        # from an onchange call (i.e. a manually crafted malicious one)
        # see: https://github.com/odoo/odoo/pull/189772#issuecomment-2548804283
        for match in DOMAIN_FIELDS_RE.finditer(self.filter_domain):
            if field := match.groupdict().get('field'):
                fields |= self.env["ir.model.fields"]._get(model, field)
        return fields