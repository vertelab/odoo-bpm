"""BPM Law Packages — Pre-configured law sets for business types.

Provides:
    bpm.law.package — A named collection of relevant laws for a business type
    bpm.law.package.line — Individual law within a package (SFS number, name, category)

Integration:
    res.company — Select active packages per company
    res.config.settings — UI to choose business type packages

The system auto-creates document.law records when a package is activated.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ── Law categories ─────────────────────────────────────────

LAW_CATEGORIES = [
    ("corporate", "Company Law"),
    ("accounting", "Accounting & Auditing"),
    ("employment", "Employment & Work Environment"),
    ("tax", "Tax & VAT"),
    ("data", "Data Protection & Privacy"),
    ("environmental", "Environmental"),
    ("product", "Product Safety & Liability"),
    ("food", "Food & Beverage"),
    ("alcohol", "Alcohol & Tobacco"),
    ("premises", "Premises & Building"),
    ("ip", "Intellectual Property"),
    ("marketing", "Marketing & Consumer"),
    ("safety", "Safety & Security"),
    ("transport", "Transport & Logistics"),
    ("other", "Other"),
]

BUSINESS_TYPES = [
    ("consulting", "Consulting Firm"),
    ("law_firm", "Law Firm / Advokatbyrå"),
    ("manufacturing", "Manufacturing"),
    ("restaurant", "Restaurant"),
    ("retail", "Retail Store / Butik"),
    ("webshop", "Web Shop / E-handel"),
]

# Size categories according to Swedish law thresholds
SIZE_CATEGORIES = [
    ("micro", "Micro (0-4 employees)"),
    ("small", "Small (5-49 employees)"),     # Skyddsombud required
    ("medium", "Medium (50-249 employees)"),  # Arbetsmiljökommitté, DPO recommended
    ("large", "Large (250+ employees)"),       # Full compliance, sustainability reporting
]

# Size thresholds that trigger specific requirements
SIZE_THRESHOLDS = [
    ("5_employees", "5+ employees — Skyddsombud required (AML 6:2)"),
    ("10_employees", "10+ employees — Arbetsanpassning/rehab (AFS 2020:5)"),
    ("50_employees", "50+ employees — Arbetsmiljökommitté (AML 6:8)"),
    ("250_employees", "250+ employees — Hållbarhetsrapport (ÅRL 6:10)"),
    ("3_more_2yr", ">3 employees avg 2yr, >1.5M balance, >3M revenue — Revisionsplikt"),
    ("250_emp_40m", "250+ emp or 40M+ revenue — GDPR DPO required"),
]


class BPMLawPackage(models.Model):
    """A pre-configured set of relevant laws for a business type.

    Example: "Consulting Firm" package contains Aktiebolagslagen,
    Bokföringslagen, GDPR, etc.
    """

    _name = "bpm.law.package"
    _description = "Law Package"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    description = fields.Text(
        string="Description",
        help="What kind of business this package is for",
    )
    business_type = fields.Selection(
        BUSINESS_TYPES, string="Business Type",
        help="Primary business type this package targets",
    )
    size_category = fields.Selection(
        SIZE_CATEGORIES, string="Recommended For",
        help="Company size this package is most relevant for. "
             "Larger packages include all laws from smaller sizes.",
        default="small",
    )
    active = fields.Boolean(default=True)

    # ── Package contents ────────────────────────────────────

    line_ids = fields.One2many(
        "bpm.law.package.line", "package_id", string="Laws",
    )
    law_count = fields.Integer(
        compute="_compute_law_count", string="Number of Laws",
    )

    # ── Track which companies use this package ──────────────

    company_ids = fields.Many2many(
        "res.company", "bpm_law_package_company_rel",
        "package_id", "company_id",
        string="Active For Companies",
        help="Companies that have activated this package",
    )

    @api.depends("line_ids")
    def _compute_law_count(self):
        for rec in self:
            rec.law_count = len(rec.line_ids)

    def action_apply_to_company(self):
        """Create document.law records for all laws in this package."""
        self.ensure_one()
        company = self.env.company

        # Add company to active list
        self.company_ids = [(4, company.id)]

        existing_sfs = self.env["document.law"].search([
            ("company_id", "=", company.id),
            ("rss_dok_id", "!=", False),
        ]).mapped("rss_dok_id")

        created = 0
        for line in self.line_ids:
            sfs_id = line.sfs_number
            if sfs_id not in existing_sfs:
                self.env["document.law"].create({
                    "company_id": company.id,
                    "rss_dok_id": sfs_id,
                    "rss_titel": line.name,
                    "rss_typ": "SFS",
                    "stage": "draft",
                    "rss_beteckning": line.sfs_number,
                    "rss_organ": line.department or "",
                    "active": True,
                })
                created += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Package Applied"),
                "message": _(
                    "'%(package)s' activated: %(created)d new laws "
                    "added to law monitoring."
                ) % {
                    "package": self.name,
                    "created": created,
                },
                "type": "success",
            },
        }


class BPMLawPackageLine(models.Model):
    """A single law within a package."""

    _name = "bpm.law.package.line"
    _description = "Law Package Line"
    _order = "category, sequence, name"

    package_id = fields.Many2one(
        "bpm.law.package", string="Package",
        required=True, ondelete="cascade",
    )
    name = fields.Char(
        string="Law Name", required=True,
        help="Full name of the law, e.g. 'Aktiebolagslag (2005:551)'",
    )
    sfs_number = fields.Char(
        string="SFS Number", required=True, index=True,
        help="Swedish Code of Statutes number, e.g. '2005:551'",
    )
    department = fields.Char(
        string="Department/Agency",
        help="Issuing government department, e.g. 'Justitiedepartementet'",
    )
    category = fields.Selection(
        LAW_CATEGORIES, string="Category", required=True,
    )
    description = fields.Text(
        string="Relevance Note",
        help="Why this law is relevant for this business type",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ── Size-based applicability ────────────────────────────

    size_category = fields.Selection(
        SIZE_CATEGORIES, string="Applies From",
        help="Company size at which this law becomes especially relevant. "
             "Used to filter packages based on company size.",
    )
    size_threshold = fields.Selection(
        SIZE_THRESHOLDS, string="Trigger Threshold",
        help="Specific legal threshold that activates this requirement",
    )
    min_employees = fields.Integer(
        string="Min Employees",
        help="Minimum number of employees for this requirement to apply",
    )

    # ── Link to actual law record ───────────────────────────

    document_law_id = fields.Many2one(
        "document.law", string="Law Record",
        help="Linked document.law record (auto-created on activation)",
        readonly=True,
    )


# ── Lagen.nu / Lagrummet.se Import ─────────────────────────

SFS_LAW_DATABASE = {
    "1977:1160": {
        "name": "Arbetsmiljölag (1977:1160)",
        "department": "Arbetsmarknadsdepartementet",
        "lagennu_url": "https://lagen.nu/1977:1160",
        "keywords": ["arbetsmiljö", "skydd", "sam"],
    },
    "2005:551": {
        "name": "Aktiebolagslag (2005:551)",
        "department": "Justitiedepartementet",
        "lagennu_url": "https://lagen.nu/2005:551",
        "keywords": ["bolag", "aktiebolag", "styrelse"],
    },
    "1999:1078": {
        "name": "Bokföringslag (1999:1078)",
        "department": "Justitiedepartementet",
        "lagennu_url": "https://lagen.nu/1999:1078",
        "keywords": ["bokföring", "redovisning"],
    },
    "1995:1554": {
        "name": "Årsredovisningslag (1995:1554)",
        "department": "Justitiedepartementet",
        "lagennu_url": "https://lagen.nu/1995:1554",
        "keywords": ["årsredovisning", "årsbokslut"],
    },
    "2023:200": {
        "name": "Mervärdesskattelag (2023:200)",
        "department": "Finansdepartementet",
        "lagennu_url": "https://lagen.nu/2023:200",
        "keywords": ["moms", "mervärdesskatt"],
    },
    "1999:1229": {
        "name": "Inkomstskattelag (1999:1229)",
        "department": "Finansdepartementet",
        "lagennu_url": "https://lagen.nu/1999:1229",
        "keywords": ["skatt", "inkomst"],
    },
    "2008:567": {
        "name": "Diskrimineringslag (2008:567)",
        "department": "Arbetsmarknadsdepartementet",
        "lagennu_url": "https://lagen.nu/2008:567",
        "keywords": ["diskriminering", "jämställdhet"],
    },
    "2006:804": {
        "name": "Livsmedelslag (2006:804)",
        "department": "Landsbygds- och infrastrukturdepartementet",
        "lagennu_url": "https://lagen.nu/2006:804",
        "keywords": ["livsmedel", "mat", "hygien"],
    },
    "2010:1622": {
        "name": "Alkohollag (2010:1622)",
        "department": "Socialdepartementet",
        "lagennu_url": "https://lagen.nu/2010:1622",
        "keywords": ["alkohol", "servering", "tillstånd"],
    },
    "1998:808": {
        "name": "Miljöbalk (1998:808)",
        "department": "Klimat- och näringslivsdepartementet",
        "lagennu_url": "https://lagen.nu/1998:808",
        "keywords": ["miljö", "avfall", "kemikalier"],
    },
    "2008:486": {
        "name": "Marknadsföringslag (2008:486)",
        "department": "Finansdepartementet",
        "lagennu_url": "https://lagen.nu/2008:486",
        "keywords": ["marknadsföring", "reklam"],
    },
    "1960:729": {
        "name": "Upphovsrättslag (1960:729)",
        "department": "Justitiedepartementet",
        "lagennu_url": "https://lagen.nu/1960:729",
        "keywords": ["upphovsrätt", "immaterialrätt", "copyright"],
    },
    "2018:218": {
        "name": "Lag med kompletterande bestämmelser till EU:s dataskyddsförordning (2018:218)",
        "department": "Justitiedepartementet",
        "lagennu_url": "https://lagen.nu/2018:218",
        "keywords": ["gdpr", "dataskydd", "personuppgifter"],
    },
    "1982:80": {
        "name": "Lag om anställningsskydd (1982:80)",
        "department": "Arbetsmarknadsdepartementet",
        "lagennu_url": "https://lagen.nu/1982:80",
        "keywords": ["las", "anställning", "uppsägning"],
    },
    "2010:900": {
        "name": "Plan- och bygglag (2010:900)",
        "department": "Landsbygds- och infrastrukturdepartementet",
        "lagennu_url": "https://lagen.nu/2010:900",
        "keywords": ["bygglov", "byggnad"],
    },
    "1915:218": {
        "name": "Avtalslag (1915:218)",
        "department": "Justitiedepartementet",
        "lagennu_url": "https://lagen.nu/1915:218",
        "keywords": ["avtal", "fullmakt"],
    },
}


class BPMLawImport(models.TransientModel):
    """Import laws from external sources (lagen.nu, lagrummet.se).

    Provides pre-populated SFS law metadata with lagen.nu URLs.
    Acts as a seed database for the law monitoring system.
    """

    _name = "bpm.law.import"
    _description = "Law Import from External Sources"

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company,
    )
    source = fields.Selection(
        [("lagennu", "lagen.nu"), ("lagrummet", "lagrummet.se")],
        default="lagennu",
    )
    sfs_numbers = fields.Text(
        string="SFS Numbers",
        help="One SFS number per line (e.g. 1977:1160). Leave empty to import all known laws.",
    )

    def action_import(self):
        """Import laws from the pre-populated database or external source."""
        self.ensure_one()

        if self.sfs_numbers:
            sfs_list = [s.strip() for s in self.sfs_numbers.split("\n") if s.strip()]
        else:
            sfs_list = list(SFS_LAW_DATABASE.keys())

        created = 0
        existing = self.env["document.law"].search([
            ("company_id", "=", self.company_id.id),
            ("rss_dok_id", "!=", False),
        ]).mapped("rss_dok_id")

        for sfs in sfs_list:
            law = SFS_LAW_DATABASE.get(sfs)
            if not law or sfs in existing:
                continue

            if sfs not in existing:
                self.env["document.law"].create({
                    "company_id": self.company_id.id,
                    "rss_dok_id": sfs,
                    "rss_titel": law["name"],
                    "rss_typ": "SFS",
                    "rss_organ": law.get("department", ""),
                    "stage": "draft",
                    "active": True,
                })
                created += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import Complete"),
                "message": _("Imported %d laws from %s.") % (
                    created,
                    dict(self._fields["source"].selection).get(self.source, self.source),
                ),
                "type": "success",
            },
        }

    def action_open_lagennu(self, sfs_number):
        """Open lagen.nu in browser for a specific law."""
        law = SFS_LAW_DATABASE.get(sfs_number, {})
        url = law.get("lagennu_url", f"https://lagen.nu/{sfs_number}")
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }
