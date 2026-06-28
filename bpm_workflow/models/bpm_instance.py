"""BPM Process Instances — runtime execution of process definitions.

Adds bpm.instance (a running process) and bpm.instance.task
(a single task within a running process) to track live execution.
"""

import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class BPMInstance(models.Model):
    """A running or completed process instance.

    Created from a bpm.workflow definition. Tracks current state,
    active tasks, timing, and references the business object this
    process is about (e.g. a sale.order, a helpdesk ticket).
    """

    _name = "bpm.instance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "BPM Process Instance"
    _order = "start_date desc"

    # ── Identity ────────────────────────────────────────────
    name = fields.Char(
        compute="_compute_name", store=True, tracking=True
    )
    workflow_id = fields.Many2one(
        "bpm.workflow", string="Process Definition",
        required=True, ondelete="restrict", tracking=True,
    )
    workflow_version = fields.Char(
        related="workflow_id.version", string="Version", store=True,
    )

    # ── State ───────────────────────────────────────────────
    state = fields.Selection(
        [
            ("running", "Running"),
            ("completed", "Completed"),
            ("terminated", "Terminated"),
            ("suspended", "Suspended"),
        ],
        default="running", tracking=True, required=True,
    )

    # ── Timing ──────────────────────────────────────────────
    start_date = fields.Datetime(
        default=lambda self: fields.Datetime.now(), required=True,
    )
    end_date = fields.Datetime(readonly=True)
    duration_hours = fields.Float(
        compute="_compute_duration", store=True,
        help="Total duration from start to completion in hours",
    )

    # ── Business Object Reference ───────────────────────────
    res_model = fields.Char(
        string="Related Model", index=True,
        help="The model this process instance is about (e.g. sale.order)",
    )
    res_id = fields.Integer(
        string="Related Record ID", index=True,
    )
    res_ref = fields.Reference(
        string="Related Record", selection="_selection_target_model",
        compute="_compute_res_ref", store=True,
    )

    # ── Who ─────────────────────────────────────────────────
    user_id = fields.Many2one(
        "res.users", string="Started By",
        default=lambda self: self.env.user, tracking=True,
    )
    process_owner_id = fields.Many2one(
        related="workflow_id.process_owner_id",
        string="Process Owner", store=True,
    )

    # ── Tasks ───────────────────────────────────────────────
    instance_task_ids = fields.One2many(
        "bpm.instance.task", "instance_id", string="Tasks",
    )
    active_tasks_count = fields.Integer(
        compute="_compute_task_counts", store=True,
    )
    completed_tasks_count = fields.Integer(
        compute="_compute_task_counts", store=True,
    )
    total_tasks_count = fields.Integer(
        compute="_compute_task_counts", store=True,
    )

    # ── Compute methods ─────────────────────────────────────

    @api.depends("workflow_id.name", "res_ref", "start_date")
    def _compute_name(self):
        for rec in self:
            base = rec.workflow_id.name or "Process"
            if rec.res_ref:
                rec.name = f"{base} — {rec.res_ref.display_name}"
            else:
                date_str = rec.start_date.strftime("%Y-%m-%d %H:%M") if rec.start_date else ""
                rec.name = f"{base} ({rec.id}) {date_str}"

    @api.depends("res_model", "res_id")
    def _compute_res_ref(self):
        for rec in self:
            if rec.res_model and rec.res_id:
                rec.res_ref = f"{rec.res_model},{rec.res_id}"
            else:
                rec.res_ref = False

    @api.depends("start_date", "end_date")
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                delta = rec.end_date - rec.start_date
                rec.duration_hours = delta.total_seconds() / 3600.0
            else:
                rec.duration_hours = 0

    @api.depends("instance_task_ids.state")
    def _compute_task_counts(self):
        for rec in self:
            tasks = rec.instance_task_ids
            rec.total_tasks_count = len(tasks)
            rec.completed_tasks_count = len(tasks.filtered(lambda t: t.state == "done"))
            rec.active_tasks_count = len(tasks.filtered(
                lambda t: t.state in ("ready", "in_progress")
            ))

    @api.model
    def _selection_target_model(self):
        """Models that can be the subject of a process."""
        return [
            ("sale.order", "Sales Order"),
            ("purchase.order", "Purchase Order"),
            ("account.move", "Invoice"),
            ("project.task", "Project Task"),
            ("helpdesk.ticket", "Helpdesk Ticket"),
            ("hr.applicant", "Applicant"),
            ("crm.lead", "Lead"),
            ("stock.picking", "Transfer"),
        ]

    # ── Actions ─────────────────────────────────────────────

    def action_start(self):
        """Create instance tasks for all start nodes and activate them."""
        self.ensure_one()
        if self.state != "running":
            raise UserError(_("Instance is not in 'running' state."))

        start_tasks = self.workflow_id.task_ids.filtered(
            lambda t: t.task_type == "start"
        )
        if not start_tasks:
            raise UserError(_("Process definition has no start node."))

        for start_task in start_tasks:
            self._create_instance_task(start_task)
            self._activate_next_tasks(start_task)

    def action_complete(self):
        """Mark as completed."""
        self.ensure_one()
        self.write({
            "state": "completed",
            "end_date": fields.Datetime.now(),
        })

    def action_terminate(self):
        """Terminate the instance and all pending tasks."""
        self.ensure_one()
        self.instance_task_ids.filtered(
            lambda t: t.state not in ("done", "skipped")
        ).write({"state": "skipped"})
        self.write({
            "state": "terminated",
            "end_date": fields.Datetime.now(),
        })

    def action_suspend(self):
        self.ensure_one()
        self.state = "suspended"

    def action_resume(self):
        self.ensure_one()
        self.state = "running"

    # ── Internal task management ────────────────────────────

    def _create_instance_task(self, definition_task):
        """Create or get existing instance task for a definition task."""
        existing = self.instance_task_ids.filtered(
            lambda t: t.task_id == definition_task
        )
        if existing:
            return existing

        assigned_to = definition_task.user_id or False
        return self.env["bpm.instance.task"].create({
            "instance_id": self.id,
            "task_id": definition_task.id,
            "name": definition_task.name,
            "task_type": definition_task.task_type,
            "assigned_to": assigned_to.id if assigned_to else False,
            "state": "ready" if definition_task.task_type == "start" else "pending",
            "sequence": definition_task.sequence,
        })

    def _activate_next_tasks(self, definition_task):
        """When a definition task is completed, activate all downstream
        tasks that have all their parents completed (AND-join logic).

        Also handles OR-join: if any parent is done, the child becomes ready.
        """
        self.ensure_one()

        # Find all children of this definition task
        for child_rel in definition_task.child_ids:
            if not child_rel.child_id:
                continue

            child_def = child_rel.child_id
            instance_child = self._create_instance_task(child_def)

            # Get all parent definition tasks of this child
            parent_def_ids = child_def.parent_ids.mapped("parent_id.id")
            if not parent_def_ids:
                # No parents (shouldn't happen except for start nodes)
                instance_child.state = "ready"
                continue

            # Check if ALL parents are done (AND-join)
            parent_instance_tasks = self.instance_task_ids.filtered(
                lambda t: t.task_id.id in parent_def_ids
            )
            all_parents_done = all(
                pt.state == "done" for pt in parent_instance_tasks
            )
            if all_parents_done:
                instance_child.state = "ready"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            # Auto-start: create instance tasks for all definition tasks
            if record.state == "running" and record.workflow_id:
                # Create all instance tasks upfront
                for def_task in record.workflow_id.task_ids:
                    inst_task = record._create_instance_task(def_task)
                    # Activate start nodes
                    if def_task.task_type == "start":
                        inst_task.state = "ready"
                    # Activate tasks whose parents are all done
                    record._activate_next_tasks(def_task)
        return records


class BPMInstanceTask(models.Model):
    """A single task within a running process instance."""

    _name = "bpm.instance.task"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "BPM Instance Task"
    _order = "sequence asc"

    # ── Identity ────────────────────────────────────────────
    name = fields.Char(string="Task Name", required=True, tracking=True)
    instance_id = fields.Many2one(
        "bpm.instance", string="Process Instance",
        required=True, ondelete="cascade", index=True,
    )
    task_id = fields.Many2one(
        "bpm.task", string="Definition Task",
        required=True, ondelete="restrict", index=True,
    )
    workflow_id = fields.Many2one(
        related="instance_id.workflow_id", string="Process",
        store=True,
    )
    sequence = fields.Integer(default=10)
    task_type = fields.Selection(
        related="task_id.task_type", string="Type", store=True,
    )

    # ── State ───────────────────────────────────────────────
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("ready", "Ready"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("skipped", "Skipped"),
        ],
        default="pending", tracking=True, required=True,
        group_expand="_read_group_state",
    )

    # ── Assignment ──────────────────────────────────────────
    assigned_to = fields.Many2one(
        "res.users", string="Assigned To", tracking=True,
        help="User responsible for completing this task",
    )
    assigned_group_id = fields.Many2one(
        "res.groups", string="Assigned Group",
        help="Group responsible for this task (used for auto-assignment)",
    )

    # ── Timing ──────────────────────────────────────────────
    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    deadline = fields.Date(
        string="Deadline",
        help="Date by which this task should be completed",
    )
    duration_hours = fields.Float(
        compute="_compute_duration", store=True,
    )

    @api.depends("started_at", "completed_at")
    def _compute_duration(self):
        for rec in self:
            if rec.started_at and rec.completed_at:
                delta = rec.completed_at - rec.started_at
                rec.duration_hours = delta.total_seconds() / 3600.0
            else:
                rec.duration_hours = 0

    def _read_group_state(self, states, domain, order):
        """Return all states for groupby, even empty ones."""
        return ["pending", "ready", "in_progress", "done", "skipped"]

    # ── Actions ─────────────────────────────────────────────

    def action_claim(self):
        """User claims the task."""
        self.ensure_one()
        if self.state not in ("ready",):
            raise UserError(_("Only ready tasks can be claimed."))
        self.write({
            "state": "in_progress",
            "assigned_to": self.env.user.id,
            "started_at": fields.Datetime.now(),
        })

    def action_assign(self, user):
        """Assign to a specific user."""
        self.ensure_one()
        self.write({
            "assigned_to": user.id,
            "state": "ready",
        })
        # Notify the assigned user
        if user and user != self.env.user:
            self.message_post(
                body=_("Assigned to %s") % user.name,
                partner_ids=[user.partner_id.id],
                subtype_xmlid="mail.mt_comment",
            )

    def action_complete(self):
        """Mark task as done and activate downstream tasks."""
        self.ensure_one()
        if self.state not in ("in_progress", "ready"):
            raise UserError(_("Only ready or in-progress tasks can be completed."))

        self.write({
            "state": "done",
            "completed_at": fields.Datetime.now(),
        })

        # Activate next tasks in the process
        self.instance_id._activate_next_tasks(self.task_id)

        # Check if all end nodes are done → complete the instance
        end_tasks = self.instance_id.instance_task_ids.filtered(
            lambda t: t.task_type == "end"
        )
        if end_tasks and all(t.state == "done" for t in end_tasks):
            self.instance_id.action_complete()

    def action_skip(self):
        """Skip this task (e.g. optional step)."""
        self.ensure_one()
        self.write({"state": "skipped"})

    def action_reopen(self):
        """Reopen a completed or skipped task."""
        self.ensure_one()
        self.write({"state": "ready", "completed_at": False})

    # ── Auto-assignment ─────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._auto_assign()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "state" in vals and vals["state"] == "ready":
            for rec in self:
                rec._auto_assign()
        return res

    def _auto_assign(self):
        """Auto-assign based on definition task's user assignment."""
        self.ensure_one()
        if self.assigned_to or self.state != "ready":
            return

        # Check definition task for default assignee
        def_task = self.task_id
        if def_task and def_task.user_id:
            self.assigned_to = def_task.user_id
