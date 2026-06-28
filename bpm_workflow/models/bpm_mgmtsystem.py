"""BPM ↔ Management System Integration (Generic).

Bridges BPM process definitions with any installed management system standard
(ISO 9001, 14001, 27001, 42001, 45001/SAM, 22000, or any future standard).

Uses runtime model discovery via ir.model — no hardcoded standard lists.
Adds a new management system module to Odoo and BPM picks it up automatically.

Architecture:
    bpm.standard.link — one generic model to link workflows to any standard entity
    Entity types auto-discovered: policy, process, clause, objective, gap, control, etc.
    mgmtsystem.action / .nonconformity / .audit — shared across all standards → direct M2O

Continuous improvement loop:
    Nonconformity → Action → Process Update → New Version → Dashboard
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ── Dynamic model discovery (runtime, no hardcoded standards) ─

# Entity suffixes that indicate management system models.
# When a model like "iso9001.policy" or "sam.clause" is installed,
# it's automatically discovered by matching these suffixes.
MGMT_ENTITY_SUFFIXES = [
    "policy",
    "process",
    "clause",
    "objective",
    "gap",
    "control",
    "soa",
    "aspect",
    "impact",
    "hazard",
    "haccp",
    "prp",
    "ccp",
    "compliance",
    "flow",
    "emergency",
    "traceability",
    "aisystem",
]


def _discover_standard_models(env):
    """Return all installed management system entity models.

    Queries ir.model at runtime — no hardcoded standard list.
    Any module that registers a model matching MGMT_ENTITY_SUFFIXES
    (e.g. iso50001.policy, custom9001.clause) is auto-discovered.

    Args:
        env: Odoo environment

    Returns:
        list of (model_name, display_label) tuples
    """
    # Build domain: model LIKE '%.policy' OR model LIKE '%.clause' OR ...
    domain = []
    for i, suffix in enumerate(MGMT_ENTITY_SUFFIXES):
        if i > 0:
            domain.insert(0, "|")
        domain.append(("model", "=like", f"%.{suffix}"))

    # Only real persistent models, not transient wizards
    domain.append(("transient", "=", False))

    models = env["ir.model"].search(domain, order="model")

    available = []
    for model in models:
        # Derive a human-readable label from the model name
        parts = model.model.split(".")
        if len(parts) >= 2:
            # Try to get module display name, fall back to prefix
            try:
                module = env["ir.module.module"].search(
                    [("name", "=", parts[0])], limit=1
                )
                module_label = (
                    module.shortdesc or module.name or parts[0]
                ) if module else parts[0]
            except Exception:
                module_label = parts[0]

            label = f"{module_label}: {model.name}"
        else:
            label = model.name

        available.append((model.model, label))

    return available


def _discover_installed_standards(env):
    """Return a summary of which management system standards are installed.

    Discovered at runtime from ir.module.module — any installed module
    that provides management system models is detected automatically.

    Returns:
        list of dicts with keys: prefix, label, module_name
    """
    # Find all mgmtsystem-related modules that are installed
    modules = env["ir.module.module"].search([
        ("state", "=", "installed"),
        "|",
        ("name", "=like", "mgmtsystem_%"),
        ("name", "=like", "iso%_%"),
    ])

    installed = []
    seen_prefixes = set()
    for mod in modules:
        # Extract standard prefix from module name
        # e.g. mgmtsystem_9001 → iso9001, mgmtsystem_14001 → iso14001
        name = mod.name

        # Try to map module name to standard prefix
        prefix = None
        label = None

        if name.startswith("mgmtsystem_"):
            std_num = name.replace("mgmtsystem_", "")
            if std_num.isdigit():
                prefix = f"iso{std_num}"
                label = mod.shortdesc or f"ISO {std_num}"
            elif std_num == "sam":
                prefix = "sam"
                label = mod.shortdesc or "ISO 45001 — Work Environment"
            else:
                # Non-standard mgmtsystem module (law, security_alert, etc.)
                # Check if it provides any entity models
                prefix = std_num
                label = mod.shortdesc or mod.name
        elif "iso" in name.lower():
            # e.g. some custom module like "my_iso_module"
            prefix = name
            label = mod.shortdesc or name
        else:
            continue

        if prefix and prefix not in seen_prefixes:
            seen_prefixes.add(prefix)
            installed.append({
                "prefix": prefix,
                "label": label,
                "module_name": name,
            })

    return installed


# ── Generic standard link model ─────────────────────────────

class BPMStandardLink(models.Model):
    """Single generic link between a BPM workflow and any management
    system entity (policy, clause, process, etc.) from any standard.

    Replaces the need for separate Many2many fields per standard.
    """

    _name = "bpm.standard.link"
    _description = "BPM → Management System Link"
    _order = "link_type, res_model, sequence"

    workflow_id = fields.Many2one(
        "bpm.workflow", string="BPM Workflow",
        required=True, ondelete="cascade", index=True,
    )
    task_id = fields.Many2one(
        "bpm.task", string="BPM Task",
        ondelete="cascade", index=True,
        help="Link at the task level (optional, overrides workflow-level)",
    )
    requirement_id = fields.Many2one(
        "bpm.requirement", string="BPM Requirement",
        ondelete="cascade", index=True,
    )

    # ── The linked entity ───────────────────────────────────

    res_model = fields.Char(
        string="Linked Model", required=True, index=True,
        help="Management system model (e.g. iso9001.clause, iso14001.policy)",
    )
    res_id = fields.Integer(
        string="Linked Record ID", required=True, index=True,
    )
    res_ref = fields.Reference(
        string="Linked Record",
        selection=lambda self: _discover_standard_models(self.env),
        compute="_compute_res_ref", store=True, readonly=False,
        required=True,
    )
    res_name = fields.Char(
        compute="_compute_res_name", string="Name",
    )

    # ── Classification ──────────────────────────────────────

    link_type = fields.Selection(
        lambda self: [(s, s.replace('_', ' ').title()) for s in MGMT_ENTITY_SUFFIXES],
        string="Link Type", required=True,
    )
    standard = fields.Char(
        compute="_compute_standard", store=True,
        string="Standard",
    )
    sequence = fields.Integer(default=10)

    @api.depends("res_model", "res_id")
    def _compute_res_ref(self):
        for rec in self:
            if rec.res_model and rec.res_id:
                rec.res_ref = f"{rec.res_model},{rec.res_id}"
            else:
                rec.res_ref = False

    @api.depends("res_ref")
    def _compute_res_name(self):
        for rec in self:
            if rec.res_ref:
                rec.res_name = rec.res_ref.display_name or str(rec.res_id)
            else:
                rec.res_name = ""

    @api.depends("res_model")
    def _compute_standard(self):
        for rec in self:
            if rec.res_model:
                prefix = rec.res_model.split(".")[0]
                # Try to get a human-readable label from ir.module.module
                try:
                    module = self.env["ir.module.module"].search(
                        [("name", "=", prefix)], limit=1
                    )
                    rec.standard = (
                        module.shortdesc or module.name or prefix
                    ) if module else prefix
                except Exception:
                    rec.standard = prefix
            else:
                rec.standard = ""


# ── Workflow-level management system links ──────────────────

class BPMWorkflow(models.Model):
    _inherit = "bpm.workflow"

    # ── Generic links ───────────────────────────────────────

    mgmt_link_ids = fields.One2many(
        "bpm.standard.link", "workflow_id",
        string="Management System Links",
        help="Links to policies, clauses, processes, objectives, etc.",
    )
    mgmt_link_count = fields.Integer(
        compute="_compute_mgmt_link_counts",
    )
    mgmt_policy_count = fields.Integer(
        compute="_compute_mgmt_link_counts",
    )
    mgmt_clause_count = fields.Integer(
        compute="_compute_mgmt_link_counts",
    )
    mgmt_process_count = fields.Integer(
        compute="_compute_mgmt_link_counts",
    )
    mgmt_objective_count = fields.Integer(
        compute="_compute_mgmt_link_counts",
    )

    # ── Shared entities (direct — same across all standards) ─

    mgmt_action_ids = fields.Many2many(
        "mgmtsystem.action", string="Improvement Actions",
        help="Management system actions that led to changes in this process",
        readonly=True,
    )
    mgmt_action_count = fields.Integer(
        compute="_compute_mgmt_counts", store=False,
    )
    mgmt_nonconformity_ids = fields.Many2many(
        "mgmtsystem.nonconformity", string="Nonconformities",
        help="Nonconformities linked to this process",
    )
    mgmt_nonconformity_count = fields.Integer(
        compute="_compute_mgmt_counts", store=False,
    )
    mgmt_audit_ids = fields.Many2many(
        "mgmtsystem.audit", string="Audits",
        help="Audits that have reviewed this process",
    )
    mgmt_last_improvement_date = fields.Date(
        string="Last Improvement", tracking=True,
    )

    # ── Installed standards info ────────────────────────────

    installed_standards = fields.Text(
        compute="_compute_installed_standards",
        help="JSON list of installed management system standards",
    )

    @api.depends("mgmt_link_ids")
    def _compute_mgmt_link_counts(self):
        for rec in self:
            links = rec.mgmt_link_ids
            rec.mgmt_link_count = len(links)
            rec.mgmt_policy_count = len(links.filtered(lambda l: l.link_type == "policy"))
            rec.mgmt_clause_count = len(links.filtered(lambda l: l.link_type == "clause"))
            rec.mgmt_process_count = len(links.filtered(lambda l: l.link_type == "process"))
            rec.mgmt_objective_count = len(links.filtered(lambda l: l.link_type == "objective"))

    @api.depends("mgmt_action_ids", "mgmt_nonconformity_ids")
    def _compute_mgmt_counts(self):
        for rec in self:
            rec.mgmt_action_count = len(rec.mgmt_action_ids)
            rec.mgmt_nonconformity_count = len(rec.mgmt_nonconformity_ids)

    def _compute_installed_standards(self):
        standards = _discover_installed_standards(self.env)
        for rec in self:
            rec.installed_standards = str(standards)

    # ── Link management helpers ─────────────────────────────

    def add_mgmt_link(self, res_model, res_id, link_type):
        """Add a management system link to this workflow."""
        self.ensure_one()
        if link_type not in MGMT_ENTITY_SUFFIXES:
            raise UserError(_("Invalid link type: %s") % link_type)
        return self.env["bpm.standard.link"].create({
            "workflow_id": self.id,
            "res_model": res_model,
            "res_id": res_id,
            "link_type": link_type,
        })

    def get_mgmt_links_by_type(self, link_type):
        """Get all links of a specific type."""
        self.ensure_one()
        return self.mgmt_link_ids.filtered(lambda l: l.link_type == link_type)

    def get_mgmt_links_by_standard(self, standard_prefix):
        """Get all links for a specific standard (e.g. 'iso14001')."""
        self.ensure_one()
        return self.mgmt_link_ids.filtered(
            lambda l: l.res_model.startswith(standard_prefix)
        )

    # ── Actions ─────────────────────────────────────────────

    def action_view_mgmt_actions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Improvement Actions"),
            "res_model": "mgmtsystem.action",
            "domain": [("id", "in", self.mgmt_action_ids.ids)],
            "view_mode": "tree,form",
        }

    def action_view_mgmt_nonconformities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nonconformities"),
            "res_model": "mgmtsystem.nonconformity",
            "domain": [("id", "in", self.mgmt_nonconformity_ids.ids)],
            "view_mode": "tree,form",
        }

    def action_view_mgmt_links(self):
        """Open all management system links for this workflow."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Management System Links"),
            "res_model": "bpm.standard.link",
            "domain": [("workflow_id", "=", self.id)],
            "view_mode": "tree,form",
            "context": {"default_workflow_id": self.id},
        }


# ── Task-level management system links ─────────────────────

class BPMTask(models.Model):
    _inherit = "bpm.task"

    mgmt_link_ids = fields.One2many(
        "bpm.standard.link", "task_id",
        string="Management System Links",
    )
    mgmt_action_id = fields.Many2one(
        "mgmtsystem.action", string="Improvement Action",
        tracking=True,
    )


class BPMRequirement(models.Model):
    _inherit = "bpm.requirement"

    mgmt_link_ids = fields.One2many(
        "bpm.standard.link", "requirement_id",
        string="Management System Links",
    )


# ── Instance-level management system links ─────────────────

class BPMInstance(models.Model):
    _inherit = "bpm.instance"

    mgmt_audit_id = fields.Many2one(
        "mgmtsystem.audit", string="Source Audit", tracking=True,
    )
    mgmt_action_id = fields.Many2one(
        "mgmtsystem.action", string="Source Action", tracking=True,
    )


# ── Extend shared management system entities ───────────────

class MgmtsystemAction(models.Model):
    _inherit = "mgmtsystem.action"

    bpm_workflow_id = fields.Many2one(
        "bpm.workflow", string="Affected Process",
    )
    bpm_task_id = fields.Many2one(
        "bpm.task", string="Affected Task",
    )
    bpm_instance_id = fields.Many2one(
        "bpm.instance", string="Process Instance",
    )
    leads_to_process_change = fields.Boolean(
        string="Leads to Process Change?", default=False,
    )

    def action_apply_to_process(self):
        """Apply this improvement action to the linked process."""
        self.ensure_one()
        if not self.bpm_workflow_id:
            raise UserError(_("No process linked to this action."))

        workflow = self.bpm_workflow_id
        workflow.button_minor_version()
        workflow.write({
            "mgmt_action_ids": [(4, self.id)],
            "mgmt_last_improvement_date": fields.Date.today(),
        })
        workflow.message_post(
            body=_(
                "**Improvement Applied**\n"
                "Action: %(action)s\n"
                "New version: %(version)s\n"
                "Applied by: %(user)s"
            ) % {
                "action": self.name,
                "version": workflow.version,
                "user": self.env.user.name,
            },
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Process Updated"),
                "message": _(
                    "Process '%(process)s' updated to version %(version)s "
                    "based on action '%(action)s'."
                ) % {
                    "process": workflow.name,
                    "version": workflow.version,
                    "action": self.name,
                },
                "type": "success",
            },
        }


class MgmtsystemNonconformity(models.Model):
    _inherit = "mgmtsystem.nonconformity"

    bpm_workflow_ids = fields.Many2many(
        "bpm.workflow",
        "mgmt_nc_bpm_workflow_rel",
        "nonconformity_id", "workflow_id",
        string="Affected Processes",
    )

    def write(self, vals):
        res = super().write(vals)
        if vals.get("state") == "done":
            for rec in self:
                for workflow in rec.bpm_workflow_ids:
                    workflow.message_post(
                        body=_(
                            "**Nonconformity Resolved**\n"
                            "%(nc)s has been resolved."
                        ) % {"nc": rec.name},
                        subtype_xmlid="mail.mt_note",
                    )
        return res
