"""BPM Dashboard — process overview, bottlenecks, and management system metrics."""

import logging
from datetime import date, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

TODAY = date.today()
WEEK_AGO = TODAY - timedelta(days=7)
MONTH_AGO = TODAY - timedelta(days=30)


class BPMDashboard(models.AbstractModel):
    """Dashboard data provider for the BPM overview page."""

    _name = "bpm.dashboard"
    _description = "BPM Dashboard"

    @api.model
    def get_dashboard_data(self):
        """Return all data needed for the dashboard.

        Returns a dict with keys:
            - summary: overview counts
            - my_tasks: current user's tasks
            - bottlenecks: longest-waiting tasks aggregated
            - workflows: per-workflow stats
            - mgmt_overview: management system summary
        """
        user = self.env.user
        domain_user_tasks = [
            ("assigned_to", "=", user.id),
            ("state", "in", ("ready", "in_progress")),
        ]

        return {
            "summary": self._get_summary(),
            "my_tasks": self._get_my_tasks(domain_user_tasks),
            "bottlenecks": self._get_bottlenecks(),
            "workflows": self._get_workflow_stats(),
            "mgmt_overview": self._get_mgmt_overview(),
        }

    def _get_summary(self):
        """Top-line numbers."""
        Instance = self.env["bpm.instance"]
        Workflow = self.env["bpm.workflow"]
        return {
            "total_workflows": Workflow.search_count([]),
            "active_workflows": Workflow.search_count([("state", "=", "approved")]),
            "running_instances": Instance.search_count([("state", "=", "running")]),
            "completed_today": Instance.search_count([
                ("end_date", ">=", TODAY),
                ("state", "=", "completed"),
            ]),
            "completed_this_week": Instance.search_count([
                ("end_date", ">=", WEEK_AGO),
                ("state", "=", "completed"),
            ]),
            "avg_duration_hours": self._get_avg_duration(),
        }

    def _get_avg_duration(self):
        """Average duration of completed instances in the last 30 days."""
        self.env.cr.execute("""
            SELECT AVG(EXTRACT(EPOCH FROM (end_date - start_date)) / 3600)
            FROM bpm_instance
            WHERE state = 'completed'
              AND end_date >= %s
              AND start_date IS NOT NULL
              AND end_date IS NOT NULL
        """, (MONTH_AGO,))
        result = self.env.cr.fetchone()[0]
        return round(result, 1) if result else 0

    def _get_my_tasks(self, domain):
        """Tasks assigned to the current user."""
        InstanceTask = self.env["bpm.instance.task"]
        tasks = InstanceTask.search(domain, order="deadline asc, sequence asc", limit=10)
        return [{
            "id": t.id,
            "name": t.name,
            "state": t.state,
            "workflow_name": t.instance_id.workflow_id.name,
            "instance_name": t.instance_id.name,
            "deadline": str(t.deadline) if t.deadline else None,
            "instance_id": t.instance_id.id,
        } for t in tasks]

    def _get_bottlenecks(self):
        """Find tasks with the longest average wait time, grouped by workflow."""
        self.env.cr.execute("""
            SELECT
                wit.instance_id,
                wit.task_id,
                bw.name AS workflow_name,
                AVG(EXTRACT(EPOCH FROM (wit.completed_at - wit.started_at)) / 3600) AS avg_hours,
                COUNT(*) AS task_count
            FROM bpm_instance_task wit
            JOIN bpm_task bt ON bt.id = wit.task_id
            JOIN bpm_workflow bw ON bw.id = bt.bpm_id
            WHERE wit.state = 'done'
              AND wit.started_at IS NOT NULL
              AND wit.completed_at IS NOT NULL
              AND wit.completed_at >= %s
            GROUP BY wit.task_id, bw.name, wit.instance_id
            ORDER BY avg_hours DESC
            LIMIT 10
        """, (MONTH_AGO,))
        rows = self.env.cr.fetchall()
        return [{
            "task_id": r[1],
            "workflow_name": r[2],
            "avg_hours": round(r[3], 1),
            "task_count": r[4],
        } for r in rows]

    def _get_workflow_stats(self):
        """Per-workflow metrics."""
        Workflow = self.env["bpm.workflow"]
        workflows = Workflow.search([("state", "=", "approved")], limit=20)
        result = []
        for wf in workflows:
            instances = self.env["bpm.instance"].search([
                ("workflow_id", "=", wf.id),
            ])
            running = len(instances.filtered(lambda i: i.state == "running"))
            completed_month = len(instances.filtered(
                lambda i: i.state == "completed" and i.end_date and i.end_date.date() >= MONTH_AGO
            ))
            total = len(instances)
            completion_pct = round(completed_month / total * 100, 1) if total else 0

            # Management system numbers
            mgmt_actions = wf.mgmt_action_count
            mgmt_nc = wf.mgmt_nonconformity_count

            result.append({
                "id": wf.id,
                "name": wf.name,
                "version": wf.version,
                "running": running,
                "completed_month": completed_month,
                "total": total,
                "completion_pct": completion_pct,
                "mgmt_actions": mgmt_actions,
                "mgmt_nonconformities": mgmt_nc,
                "last_improvement": str(wf.mgmt_last_improvement_date) if wf.mgmt_last_improvement_date else None,
            })
        return result

    def _get_mgmt_overview(self):
        """Management system summary linked to BPM."""
        Action = self.env["mgmtsystem.action"]
        Nonconformity = self.env["mgmtsystem.nonconformity"]
        Workflow = self.env["bpm.workflow"]

        return {
            "open_actions": Action.search_count([("state", "=", "open")]),
            "actions_with_process": Action.search_count([
                ("state", "=", "open"),
                ("bpm_workflow_id", "!=", False),
            ]),
            "actions_leading_to_change": Action.search_count([
                ("leads_to_process_change", "=", True),
            ]),
            "open_nonconformities": Nonconformity.search_count([
                ("state", "!=", "done"),
            ]),
            "processes_with_actions": Workflow.search_count([
                ("mgmt_action_ids", "!=", False),
            ]),
            "processes_needing_review": Workflow.search_count([
                ("state", "=", "approved"),
                ("mgmt_last_improvement_date", "=", False),
            ]),
        }


class BPMDashboardAction(models.TransientModel):
    """Client action to render the dashboard."""

    _name = "bpm.dashboard.action"
    _description = "BPM Dashboard Action"

    def action_open_dashboard(self):
        """Open the BPM dashboard view."""
        return {
            "type": "ir.actions.client",
            "tag": "bpm_dashboard",
            "name": _("BPM Dashboard"),
        }
