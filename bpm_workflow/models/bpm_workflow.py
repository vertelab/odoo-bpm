import base64
import logging
from secrets import choice

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools.misc import file_path
from odoo.addons.base.models.avatar_mixin import get_hsl_from_seed

_logger = logging.getLogger(__name__)

workflow_icon ="""<svg height="800px" width="800px" version="1.1" id="图层_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" 
	 viewBox="0 0 40 40" enable-background="new 0 0 40 40" xml:space="preserve">
<g>
	<g>
		<g>
			<g>
				<path fill="#875a7b" d="M20,22.5c-1.4,0-2.5-1.1-2.5-2.5s1.1-2.5,2.5-2.5s2.5,1.1,2.5,2.5S21.4,22.5,20,22.5z M20,18.5
					c-0.8,0-1.5,0.7-1.5,1.5s0.7,1.5,1.5,1.5s1.5-0.7,1.5-1.5S20.8,18.5,20,18.5z"/>
			</g>
			<g>
				<path fill="#231815" d="M20.7,28.5h-1.3c-0.6,0-1.2-0.5-1.2-1.2v-1c-0.4-0.1-0.8-0.3-1.2-0.5c-0.1,0-0.2,0-0.2,0l-0.7,0.7
					c-0.4,0.4-1.2,0.4-1.7,0l-1-1c-0.5-0.5-0.5-1.2,0-1.7l0.7-0.7c0.1-0.1,0-0.2,0-0.2c-0.2-0.3-0.3-0.7-0.4-1
					c0-0.1-0.1-0.1-0.2-0.1h-0.9c-0.6,0-1.2-0.5-1.2-1.2v-1.3c0-0.6,0.5-1.2,1.2-1.2h0.9c0.1,0,0.1-0.1,0.2-0.1
					c0.1-0.4,0.3-0.7,0.4-1c0-0.1,0-0.1,0-0.2l-0.7-0.7c-0.5-0.5-0.5-1.2,0-1.7l1-1c0.4-0.4,1.2-0.4,1.7,0l0.7,0.7
					c0.1,0.1,0.1,0.1,0.2,0c0.3-0.2,0.7-0.3,1-0.4c0.1,0,0.1-0.1,0.1-0.2v-0.9c0-0.6,0.5-1.2,1.2-1.2h1.3c0.6,0,1.2,0.5,1.2,1.2v0.9
					c0,0.1,0.1,0.1,0.1,0.2c0.3,0.1,0.7,0.3,1,0.4c0.1,0,0.2,0,0.2,0l0.7-0.7c0.4-0.4,1.2-0.4,1.7,0l1,1c0.5,0.5,0.5,1.2,0,1.7
					l-0.7,0.7c-0.1,0.1,0,0.2,0,0.2c0.2,0.3,0.3,0.7,0.4,1c0,0.1,0.1,0.1,0.2,0.1h0.9c0.6,0,1.2,0.5,1.2,1.2v1.3
					c0,0.6-0.5,1.2-1.2,1.2h-0.9c-0.1,0-0.1,0.1-0.2,0.1c-0.1,0.4-0.3,0.7-0.4,1c0,0.1,0,0.1,0,0.2l0.7,0.7c0.5,0.5,0.5,1.2,0,1.7
					l-1,1c-0.4,0.4-1.2,0.4-1.7,0l-0.7-0.7c-0.1-0.1-0.1-0.1-0.2,0c-0.3,0.2-0.7,0.3-1,0.4c-0.1,0-0.1,0.1-0.1,0.2v0.9
					C21.8,28,21.3,28.5,20.7,28.5z M16.9,24.8c0.2,0,0.4,0,0.6,0.1c0.4,0.2,0.9,0.4,1.3,0.5c0.2,0.1,0.4,0.3,0.4,0.5v1.4
					c0,0.1,0.1,0.2,0.2,0.2h1.3c0.1,0,0.2-0.1,0.2-0.2v-0.9c0-0.5,0.3-1,0.8-1.1c0.3-0.1,0.6-0.2,0.9-0.4c0.5-0.2,1-0.2,1.4,0.2
					l0.7,0.7c0.1,0.1,0.2,0.1,0.2,0l1-1c0.1-0.1,0.1-0.2,0-0.2l-0.7-0.7c-0.4-0.4-0.4-0.9-0.2-1.4c0.1-0.3,0.3-0.6,0.4-0.9
					c0.2-0.5,0.6-0.8,1.1-0.8h0.9c0.1,0,0.2-0.1,0.2-0.2v-1.3c0-0.1-0.1-0.2-0.2-0.2h-0.9c-0.5,0-1-0.3-1.1-0.8
					c-0.1-0.3-0.2-0.6-0.4-0.9c-0.2-0.5-0.2-1,0.2-1.4l0.7-0.7c0.1-0.1,0.1-0.2,0-0.2l-1-1c-0.1-0.1-0.2-0.1-0.2,0l-0.7,0.7
					c-0.4,0.3-0.9,0.4-1.4,0.2c-0.3-0.1-0.6-0.3-0.9-0.4c-0.5-0.2-0.8-0.6-0.8-1.1v-0.9c0-0.1-0.1-0.2-0.2-0.2h-1.3
					c-0.1,0-0.2,0.1-0.2,0.2v0.9c0,0.5-0.3,1-0.8,1.1c-0.3,0.1-0.6,0.2-0.9,0.4c-0.5,0.2-1,0.2-1.4-0.2l-0.7-0.7
					c-0.1-0.1-0.2-0.1-0.2,0l-1,1c-0.1,0.1-0.1,0.2,0,0.2l0.7,0.7c0.4,0.4,0.4,0.9,0.2,1.4c-0.1,0.3-0.3,0.6-0.4,0.9
					c-0.2,0.5-0.6,0.8-1.1,0.8h-0.9c-0.1,0-0.2,0.1-0.2,0.2v1.3c0,0.1,0.1,0.2,0.2,0.2h0.9c0.5,0,1,0.3,1.1,0.8
					c0.1,0.3,0.2,0.6,0.4,0.9c0.2,0.5,0.2,1-0.2,1.4l-0.7,0.7c-0.1,0.1-0.1,0.2,0,0.2l1,1c0.1,0.1,0.2,0.1,0.2,0l0.7-0.7
					C16.3,24.9,16.6,24.8,16.9,24.8z"/>
			</g>
		</g>
	</g>
</g>
</svg>"""

class BPMWorkflow(models.Model):
    _name = 'bpm.workflow'
    _inherit = ['mermaid.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'BPM Workflow'

    author_id = fields.Many2one('res.users', string="Author",tracking=True)
    active = fields.Boolean(string='Active', default=True)
    duration_tracking = fields.Float(string='Duration Tracking')
    parent_id = fields.Many2one(comodel_name='bpm.workflow',string="Parent BPM",help="")
    company_id = fields.Many2one(comodel_name='res.company',string="Company",help="") 
    name = fields.Char(string="Titel", required=True)
    description = fields.Text(string="Description",help="Purpuse")
    image_128 = fields.Image("Image", max_width=128, max_height=128, compute="_compute_image_128")
    version = fields.Char(string="Version", default="1.0",readonly=True,tracking=True)
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
    requirement_ids = fields.One2many(comodel_name='bpm.requirement', inverse_name='bpm_id', string="Requirements",
                                      help="")
    task_ids = fields.One2many(comodel_name='bpm.task', inverse_name='bpm_id', string="Tasks", help="")
    uuid = fields.Char('UUID', size=50, default=lambda self:self._generate_random_token(), copy=False)
    requirements_count = fields.Integer(string="Total Requirements", compute='_compute_requirements_counts')
    closed_requirements_count = fields.Integer(string="Closed Requirements", compute='_compute_requirements_counts')
    requirements_percentage = fields.Float(string="Requirements Completion %", compute='_compute_requirements_counts')

    tasks_count = fields.Integer(string="Total Tasks", compute='_compute_tasks_counts')
    closed_tasks_count = fields.Integer(string="Closed Tasks", compute='_compute_tasks_counts')
    tasks_percentage = fields.Float(string="Tasks Completion %", compute='_compute_tasks_counts')

    bpm_diagram_type = fields.Selection([
        ('flowchart TD', 'flowchart TD'), ('stateDiagram', 'stateDiagram')
    ], string="Diagram Type", default='flowchart TD')

    @api.model
    def _generate_random_token(self):
        return ''.join(choice('abcdefghijkmnopqrstuvwxyzABCDEFGHIJKLMNPQRSTUVWXYZ23456789') for _i in range(10))

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'approved':
            self.approved_by_id = self.env.user.id
            self.date = fields.Date.today()
        else:
            self.approved_by_id = False

    @api.depends('image_128', 'uuid')
    def _compute_image_128(self):
        for record in self:
            record.image_128 = record.image_128 or record._generate_image()

    @api.depends('task_ids')
    def _compute_tasks_counts(self):
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

    def _generate_image(self):
        avatar = workflow_icon
        bgcolor = get_hsl_from_seed(self.uuid)
        avatar = avatar.replace('fill="#875a7b"', f'fill="{bgcolor}"')
        return base64.b64encode(workflow_icon.encode())

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

    def action_tasks(self):
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

    # def _mermaid_prompt(self):
    #     mermaid_prompt = super()._mermaid_prompt()
    #
    #     if self.task_ids:
    #         tasks = "\nTasks:\n"
    #         task_lines = [
    #             f"- Name: {actor.name}" +
    #             (f"\n  Role: {actor.role}" if hasattr(actor, 'role') and actor.role else "") +
    #             (f"\n  Goal: {actor.goal}" if hasattr(actor, 'goal') and actor.goal else "")
    #             for actor in self.task_ids
    #         ]
    #         tasks += "\n".join(task_lines)
    #         mermaid_prompt += tasks
    #
    #     return mermaid_prompt

    def action_generate_diagram(self):
        """Generate Mermaid diagram based on diagram type"""
        self.ensure_one()

        if not self.task_ids:
            self.mermaid_editor = f"<pre>{self.bpm_diagram_type or 'flowchart TD'}\n    Start[No tasks defined]</pre>"
            return

        if self.bpm_diagram_type == 'stateDiagram':
            self.mermaid_editor = f'<pre>{self._generate_state_diagram()}</pre>'
        else:  # Default to flowchart TD
            self.mermaid_editor = f'<pre>{self._generate_flowchart()}</pre>'

    def _generate_flowchart(self):
        """Generate Mermaid flowchart (TD or LR)"""
        diagram_type = self.bpm_diagram_type or 'flowchart TD'
        lines = [diagram_type, ""]

        # Map task types to Mermaid node shapes
        shape_map = {
            'start': ('[', ']'),  # Rectangle
            'task': ('[', ']'),  # Rectangle
            'decision': ('{', '}'),  # Diamond
            'end': ('([', '])'),  # Stadium
        }

        # Generate node definitions
        lines.append("    %% Nodes")
        for task in self.task_ids.sorted('sequence'):
            node_id = f"T{task.id}"
            start_shape, end_shape = shape_map.get(task.task_type, ('[', ']'))
            node_label = task.name
            lines.append(f"    {node_id}{start_shape}{node_label}{end_shape}")

        lines.append("")
        lines.append("    %% Connections")

        # Process all parent-child relationships using child_ids
        for task in self.task_ids.sorted('sequence'):
            for child in task.child_ids: 
                parent_id = f"T{task.id}"
                child_id = f"T{child.child_id.id}"

                if task.task_type == 'decision':
                    lines.append(f"    {parent_id} -->|{child.option if child.option else "Option"}| {child_id}")
                else:
                    lines.append(f"    {parent_id} --> {child_id}")

        return '\n'.join(lines)

    def _generate_state_diagram(self):
        """Generate Mermaid state diagram"""
        lines = ["stateDiagram-v2", ""]

        lines.append("    %% Transitions")

        # Process all parent-child relationships
        for task in self.task_ids.sorted('sequence'):
            for child in task.child_ids:
                parent_state = task.name.replace(' ', '_')
                child_state = child.child_id.name.replace(' ', '_')

                lines.append(f"    {parent_state} --> {child_state}")

        # Connect any orphan end tasks to [*]
        end_tasks = self.task_ids.filtered(lambda t: t.task_type == 'end' and not t.parent_id)
        for end_task in end_tasks:
            end_state = end_task.name.replace(' ', '_')
            lines.append(f"    {end_state} --> [*]")

        return '\n'.join(lines)