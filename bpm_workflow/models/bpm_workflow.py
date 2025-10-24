from datetime import datetime, timedelta 
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
import re
import html
from bs4 import BeautifulSoup

import logging

_logger = logging.getLogger(__name__)


# class MermaidMixin(models.AbstractModel):
#     _name = 'mermaid.mixin'
#     _description = 'Mermaid Diagram Mixin'
#
#
#     _mermaid_keywords = r"^(graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|flowchart|pie|journey|gantt|gitGraph)\b"
#
#     mermaid_editor = fields.Html(string="Editor", copy=False)
#
#
#
#     def wrap_mermaid_in_pre(self, mermaid_editor):
#         """
#         Finds Mermaid diagrams in HTML content and wraps them inside <pre> tags.
#
#         Args:
#             mermaid_editor (str): The raw HTML content.
#
#         Returns:
#             str: Modified HTML with Mermaid diagrams wrapped in <pre>.
#         """
#         if not mermaid_editor:
#             return ""
#
#         soup = BeautifulSoup(mermaid_editor, "html.parser")
#
#         # Check for existing pre tags with mermaid content
#         if soup.find('pre', class_='mermaid'):
#             return str(soup)
#
#         # Find potential Mermaid blocks
#         potential_blocks = [tag for tag in soup.find_all(["p", "div"])
#                             if re.search(self._mermaid_keywords, tag.get_text().lstrip(), re.MULTILINE)]
#
#         # Process each potential block
#         for start_tag in potential_blocks:
#             diagram_content = []
#             siblings_to_remove = []
#             current_tag = start_tag
#
#             # Process starting tag
#             for child in BeautifulSoup(str(current_tag), "html.parser").find_all(string=True):
#                 if child.strip():
#                     diagram_content.append(html.unescape(str(child)))
#
#             # Process potential siblings
#             next_tag = current_tag.next_sibling
#             while next_tag and hasattr(next_tag, 'name') and next_tag.name in ['p', 'div']:
#                 if re.search(self._mermaid_keywords, next_tag.get_text().lstrip(), re.MULTILINE):
#                     break
#
#                 for child in BeautifulSoup(str(next_tag), "html.parser").find_all(string=True):
#                     if child.strip():
#                         diagram_content.append(html.unescape(str(child)))
#
#                 siblings_to_remove.append(next_tag)
#                 next_tag = next_tag.next_sibling
#
#             # Create pre tag and replace original tag
#             pre_tag = soup.new_tag("pre")
#             pre_tag.string = "\n".join(diagram_content)
#             pre_tag['class'] = 'mermaid'
#             start_tag.replace_with(pre_tag)
#
#             # Remove siblings that were processed
#             for sibling in siblings_to_remove:
#                 sibling.extract()  # extract() is an alternative to decompose()
#
#         return str(soup)
#
#     @api.depends('mermaid_editor')
#     def _compute_mermaid_editor(self):
#         """
#         Computes the Mermaid diagram text and wraps it in <pre> tags if needed.
#         Only processes content that appears to be Mermaid diagrams.
#         """
#         for rec in self:
#             # Skip empty content or when called from our own update
#             if not rec.mermaid_editor:
#                 rec.mermaid_diagram = ""
#                 continue
#
#             soup = BeautifulSoup(rec.mermaid_editor, "html.parser")
#
#             # Check for existing pre tag with mermaid content
#             pre_tag = soup.find('pre', class_='mermaid')
#             if pre_tag:
#                 rec.mermaid_diagram = pre_tag.get_text()
#                 continue
#
#             # Check if content appears to be mermaid format
#             text_content = soup.get_text('\n', strip=True)
#             if not re.search(self._mermaid_keywords, text_content, re.MULTILINE):
#                 rec.mermaid_diagram = ""
#                 continue
#
#             # Extract text preserving structure and indentation
#             text_content = soup.get_text('\n', strip=False).replace('\xa0', ' ')
#             rec.mermaid_diagram = text_content
#
#             # Wrap in pre tags
#             wrapped_content = self.wrap_mermaid_in_pre(rec.mermaid_editor)
#             if wrapped_content != rec.mermaid_editor:
#                 rec.mermaid_editor = wrapped_content
#
#     mermaid_diagram = fields.Text(string="Diagram", compute=_compute_mermaid_editor, copy=False)

class BPMWorkflow(models.Model):
    _name = 'bpm.workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mermaid.mixin', ]
    _description = 'BPM Workflow'

    # duration_tracking = fields.Json(string='Duration Tracking')
    active = fields.Boolean(string='Active', default=True)
    parent_id = fields.Many2one(comodel_name='bpm.workflow',string="Parent BPM",help="")
    company_id = fields.Many2one(comodel_name='res.company',string="Company",help="", default=lambda self: self.env.company)
    name = fields.Char(string="Titel", required=True)
    description = fields.Text(string="Description",help="Purpose")
    version = fields.Char(string="Version", default="1.0",readonly=True,tracking=True)
    author_id = fields.Many2one('res.users', string="Author",tracking=True)
    process_owner_id = fields.Many2one('res.users', string="Process Owner",tracking=True)
    approved_by_id = fields.Many2one('res.users', string="Approved By",readonly=True,tracking=True)
    date = fields.Date(string="Date", default=fields.Date.today,readonly=True,tracking=True)
    goals = fields.Text(string="Goal")
    success_criteria = fields.Text(string="Success Criteria")
    dependencies = fields.Text(string="Dependencies")
    risks = fields.Text(string="Risks")
    document_type = fields.Selection([
        ('module', 'Module'),
        ('other', 'Other')],
        string="Type",
        default='module',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('deprecated', 'Deprecated')],
        string="State",
        default='draft',
        tracking=True
    )
    requirement_ids = fields.One2many(comodel_name='bpm.requirement',inverse_name='bpm_id',string="Requirements",help="")
    task_ids = fields.One2many(comodel_name='bpm.task',inverse_name='bpm_id',string="Tasks",help="")

    requirements_count = fields.Integer(string="Total Requirements", compute='_compute_requirements_counts')
    closed_requirements_count = fields.Integer(string="Closed Requirements", compute='_compute_requirements_counts')
    requirements_percentage = fields.Float(string="Requirements Completion %", compute='_compute_requirements_counts')

    tasks_count = fields.Integer(string="Total Tasks", compute='_compute_tasks_counts')
    closed_tasks_count = fields.Integer(string="Closed Tasks", compute='_compute_tasks_counts')
    tasks_percentage = fields.Float(string="Tasks Completion %", compute='_compute_tasks_counts')

    @api.model
    def _selection_target_model(self):
        return [(model.model, model.name) for model in self.env['ir.model'].sudo().search([])]

    res_id = fields.Integer(
        string="Resource ID",
        required=False)

    # res_name = fields.Char(
    #     string='Resource name',
    #     compute='_compute_res_name',
    #     store=True)

    res_model_id = fields.Many2one(
        'ir.model',
        'Related Document Model',
        ondelete='cascade')
    res_model = fields.Char(
        string='Document Model',
        related='res_model_id.model',
        store=True,
        readonly=True)
    resource_ref = fields.Reference(
        string='Record',
        selection='_selection_target_model',
        compute='_compute_resource_ref',
        inverse='_set_resource_ref')

    @api.depends('res_model', 'res_id')
    def _compute_resource_ref(self):
        for line in self:
            if line.res_model and line.res_model:
                # Exclude records that can't be read (eg: multi-company ir.rule)
                try:
                    self.env[line.res_model].browse(line.res_id).check_access('read')
                    line.resource_ref = '%s,%s' % (line.res_model, line.res_id or 0)
                except Exception:
                    line.resource_ref = None
            else:
                line.resource_ref = None

    def _set_resource_ref(self):
        for line in self:
            if line.resource_ref:
                line.res_id = line.resource_ref.id

    # @api.depends('res_model', 'res_id')
    # def _compute_res_name(self):
    #     for line in self:
    #         if not line.res_id or not line.res_model:
    #             continue
    #         record = self.env[line.res_model].sudo().browse(line.res_id)
    #         if not record.exists():
    #             continue
    #         name = record.display_name
    #         line.res_name = name if name else f'{line.res_model_id.name}/{line.res_id}'

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'approved':
            self.approved_by_id = self.env.user.id
            self.date = fields.Date.today()
        else:
            self.approved_by_id = False

    @api.depends('task_ids')
    def _compute_tasks_counts(self):
        for record in self:
            total = len(record.task_ids.filtered(lambda r: r.priority == 'should'))
            closed = len(record.task_ids.filtered(lambda f: f.state == 'done'))
            record.tasks_count = total
            record.closed_tasks_count = closed
            record.tasks_percentage = (closed / total * 100) if total else 0.0

    @api.depends('requirement_ids')
    def _compute_requirements_counts(self):
        for record in self:
            total = len(record.requirement_ids.filtered(lambda r: r.priority == 'should'))
            closed = len(record.requirement_ids.filtered(lambda r: r.state == 'done'))
            record.requirements_count = total
            record.closed_requirements_count = closed
            record.requirements_percentage = 0.0
            if total > 0:
                record.requirements_percentage = (closed / total) * 100


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
          'view_mode': 'list,form',
          'target': 'current',
          'context': {
              'default_bpm_id': self.id
          }
      }

    def action_requirements(self):
      return {
          'type': 'ir.actions.act_window',
          'name': 'Requirements',
          'res_model': 'bpm.requirement',
          'domain': [('bpm_id', '=', self.id)],
          'view_mode': 'list,form',
          'target': 'current',
      }



