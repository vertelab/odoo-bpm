"""Extend res.company and res.config.settings for law package selection."""

from odoo import _, api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    law_package_ids = fields.Many2many(
        "bpm.law.package", "bpm_law_package_company_rel",
        "company_id", "package_id",
        string="Active Law Packages",
        help="Pre-configured law packages for this company's business type",
    )
    law_package_business_types = fields.Selection(
        related="law_package_ids.business_type",
        string="Business Types",
        readonly=True,
    )

    def action_apply_all_packages(self):
        """Apply all selected law packages to this company."""
        for company in self:
            for package in company.law_package_ids:
                package.with_context(allowed_company_ids=[company.id]).action_apply_to_company()


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    law_package_ids = fields.Many2many(
        related="company_id.law_package_ids",
        string="Law Packages",
        readonly=False,
        help="Select which law packages to activate for your company. "
             "Choose one or more based on your business activities.",
    )
    law_package_business_type = fields.Selection(
        [("consulting", "Consulting Firm"), ("manufacturing", "Manufacturing"),
         ("restaurant", "Restaurant")],
        string="Primary Business Type",
        help="Quick-select: choose your main business type to load relevant laws",
    )

    def action_select_business_type(self):
        """Quick-select law packages based on business type."""
        self.ensure_one()
        if self.law_package_business_type:
            package = self.env["bpm.law.package"].search([
                ("business_type", "=", self.law_package_business_type),
            ], limit=1)
            if package:
                self.law_package_ids = [(4, package.id)]
                package.action_apply_to_company()
