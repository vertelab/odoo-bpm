import logging
from lxml import etree

from odoo import api, fields, models
from odoo.tools.misc import frozendict

_logger = logging.getLogger(__name__)

class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    bpm_task_ids = fields.Many2many(
        "bpm.task",
        compute="_compute_bpm_task_ids",
        readonly=True,
        string="BPM Tasks"
    )

    bpm_task_count = fields.Integer(compute="_compute_bpm_task_count")

    @api.depends_context('uid')
    def _compute_bpm_task_ids(self):
        """Get BPM tasks based on trigger_type, model, and domain"""
        for record in self:
            tasks = self.env['bpm.task'].search([
                ('trigger_type', '=', 'chatter'),
                ('model_name', '=', record._name),
            ])

            valid_tasks = self.env['bpm.task']
            for task in tasks:
                if task.filter_domain:
                    try:
                        domain = eval(task.filter_domain)
                        if record.filtered_domain(domain):
                            valid_tasks |= task
                    except Exception as e:
                        print(f"Invalid domain on task {task.id}: {e}")
                        _logger.warning(f"Invalid domain on task {task.id}: {e}")
                else:
                    valid_tasks |= task

            print(f"Found {len(valid_tasks)} tasks for {record._name} ID {record.id}: {valid_tasks.ids}")
            record.bpm_task_ids = valid_tasks

    @api.depends("bpm_task_ids")
    def _compute_bpm_task_count(self):
        for record in self:
            record.bpm_task_count = len(record.bpm_task_ids)

    def _get_bpm_task_count_domain(self):
        return [("res_model", "=", self._name), ("res_id", "=", self.id)]

    def _get_bpm_task_context(self):
        return {}

    def action_view_bpm_task(self):
        self.ensure_one()
        action = self.env.ref("bpm_workflow.action_bpm_task").read()[0]

        # Use the computed bpm_task_ids
        action["domain"] = [('id', 'in', self.bpm_task_ids.ids)]
        action["context"] = self._get_bpm_task_context()
        return action

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == "form" and self.env.user.has_group(
                "bpm_workflow.group_bpm_user"
        ):
            View = self.env["ir.ui.view"]
            if view_id and res.get("base_model", self._name) != self._name:
                View = View.with_context(base_model_name=res["base_model"])
            doc = etree.XML(res["arch"])
            all_models = res["models"].copy()

            for node in doc.xpath("/form/chatter"):
                # Add bpm_task_count field
                new_node = etree.fromstring(
                    "<field name='bpm_task_count' invisible='1'/>"
                )
                new_arch, new_models = View.postprocess_and_fields(new_node, self._name)
                new_node = etree.fromstring(new_arch)
                for model in list(filter(lambda x: x not in all_models, new_models)):
                    if model not in res["models"]:
                        all_models[model] = new_models[model]
                    else:
                        all_models[model] = res["models"][model]
                node.addprevious(new_node)

                # Add bpm_task_ids field (THIS IS THE FIX)
                ids_node = etree.fromstring(
                    "<field name='bpm_task_ids' invisible='1'/>"
                )
                ids_arch, ids_models = View.postprocess_and_fields(ids_node, self._name)
                ids_node = etree.fromstring(ids_arch)
                for model in list(filter(lambda x: x not in all_models, ids_models)):
                    if model not in res["models"]:
                        all_models[model] = ids_models[model]
                    else:
                        all_models[model] = res["models"][model]
                node.addprevious(ids_node)

            res["arch"] = etree.tostring(doc)
            res["models"] = frozendict(all_models)
        return res

    @api.model
    def _get_view_fields(self, view_type, models):
        result = super()._get_view_fields(view_type, models)
        if view_type == "form" and self.env.user.has_group(
                "bpm_workflow.group_bpm_user"
        ):
            result[self._name].add("bpm_task_count")
            result[self._name].add("bpm_task_ids")  # ADD THIS LINE
        return result