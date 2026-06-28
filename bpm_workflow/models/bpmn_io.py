"""BPMN 2.0 XML import/export for Odoo BPM.

Provides bidirectional conversion between bpm.workflow/bpm.task models
and standard BPMN 2.0 XML format for interoperability with Camunda,
Bizagi, Signavio, and other BPMN-compatible tools.

BPMN 2.0 XML namespace: http://www.omg.org/spec/BPMN/20100524/MODEL
"""

import logging
from io import BytesIO
from xml.etree import ElementTree as ET

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMN_DI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

ET.register_namespace("", BPMN_NS)
ET.register_namespace("bpmndi", BPMN_DI_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("di", DI_NS)

# Mapping between BPM task types and BPMN elements
TASK_TYPE_TO_BPMN = {
    "start": "startEvent",
    "end": "endEvent",
    "task": "task",
    "decision": "exclusiveGateway",
}

BPMN_TO_TASK_TYPE = {v: k for k, v in TASK_TYPE_TO_BPMN.items()}


class BPMWorkflow(models.Model):
    _inherit = "bpm.workflow"

    bpmn_xml = fields.Text(
        string="BPMN 2.0 XML",
        compute="_compute_bpmn_xml",
        store=False,
        help="Process definition in BPMN 2.0 XML format",
    )

    def _compute_bpmn_xml(self):
        for record in self:
            record.bpmn_xml = record.export_bpmn()

    def export_bpmn(self):
        """Export the workflow as BPMN 2.0 XML.

        Returns:
            str: BPMN 2.0 XML string
        """
        self.ensure_one()

        root = ET.Element(f"{{{BPMN_NS}}}definitions")
        root.set("id", f"Definitions_{self.id}")
        root.set("targetNamespace", "http://bpmn.io/schema/bpmn")
        root.set("exporter", "Odoo BPM")
        root.set("exporterVersion", "1.0")

        # Create process element
        process = ET.SubElement(root, f"{{{BPMN_NS}}}process")
        process.set("id", f"Process_{self.id}")
        process.set("name", self.name or "Untitled Process")
        process.set("isExecutable", "true")

        tasks = self.task_ids.sorted("sequence")

        # Export all tasks as BPMN elements
        for task in tasks:
            bpmn_element = TASK_TYPE_TO_BPMN.get(task.task_type, "task")
            elem = ET.SubElement(process, f"{{{BPMN_NS}}}{bpmn_element}")
            elem.set("id", f"Activity_{task.id}")
            elem.set("name", task.name or "")

            if task.task_type == "decision":
                elem.set("gatewayDirection", "Diverging")

        # Export sequence flows (child relationships)
        for task in tasks:
            source_ref = f"Activity_{task.id}"
            for child in task.child_ids:
                if not child.child_id:
                    continue
                target_ref = f"Activity_{child.child_id.id}"

                flow = ET.SubElement(process, f"{{{BPMN_NS}}}sequenceFlow")
                flow.set("id", f"Flow_{task.id}_{child.child_id.id}")
                flow.set("sourceRef", source_ref)
                flow.set("targetRef", target_ref)

                if child.option:
                    flow.set("name", child.option)

        # Add BPMN DI (diagram interchange) for visual layout
        diagram = ET.SubElement(root, f"{{{BPMN_DI_NS}}}BPMNDiagram")
        diagram.set("id", f"BPMNDiagram_{self.id}")
        plane = ET.SubElement(diagram, f"{{{BPMN_DI_NS}}}BPMNPlane")
        plane.set("id", f"BPMNPlane_{self.id}")
        plane.set("bpmnElement", f"Process_{self.id}")

        # Auto-layout: position nodes in a grid
        cols = 3
        for i, task in enumerate(tasks):
            shape = ET.SubElement(plane, f"{{{BPMN_DI_NS}}}BPMNShape")
            shape.set("id", f"BPMNShape_{task.id}")
            shape.set("bpmnElement", f"Activity_{task.id}")

            bounds = ET.SubElement(shape, f"{{{DC_NS}}}Bounds")
            x = 100 + (i % cols) * 200
            y = 100 + (i // cols) * 120
            bounds.set("x", str(x))
            bounds.set("y", str(y))
            bounds.set("width", "100")
            bounds.set("height", "80")

        # Add edges
        edge_index = 0
        for task in tasks:
            for child in task.child_ids:
                if not child.child_id:
                    continue
                edge = ET.SubElement(plane, f"{{{BPMN_DI_NS}}}BPMNEdge")
                edge.set("id", f"BPMNEdge_{edge_index}")
                edge.set("bpmnElement", f"Flow_{task.id}_{child.child_id.id}")
                edge_index += 1

        # Return pretty-printed XML
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode")

    def action_export_bpmn(self):
        """Download BPMN 2.0 XML file."""
        self.ensure_one()
        xml_content = self.export_bpmn()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/bpm.workflow/{self.id}/bpmn_file/{self.name}.bpmn?download=true",
            "target": "self",
        }

    def import_bpmn(self, xml_content):
        """Import a BPMN 2.0 XML process definition into this workflow.

        Args:
            xml_content (str): BPMN 2.0 XML string

        Raises:
            UserError: If XML is invalid or missing required elements
        """
        self.ensure_one()

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise UserError(_("Invalid XML: %s") % str(e))

        # Find namespace
        ns = {"bpmn": BPMN_NS}
        # Try without namespace too (some tools omit it)
        process = root.find(f"{{{BPMN_NS}}}process") or root.find(".//process")
        if process is None:
            raise UserError(_("No <process> element found in BPMN XML"))

        process_name = process.get("name", "Imported Process")
        if not self.name:
            self.name = process_name

        # Clear existing tasks
        self.task_ids.unlink()

        # Phase 1: Create tasks from BPMN elements
        task_map = {}  # bpmn_id → bpm.task record
        sequence = 0

        for child in process:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            task_type = BPMN_TO_TASK_TYPE.get(tag, "task")
            elem_id = child.get("id", "")
            elem_name = child.get("name", "") or tag

            task = self.env["bpm.task"].create(
                {
                    "bpm_id": self.id,
                    "name": elem_name,
                    "task_type": task_type,
                    "sequence": sequence,
                    "state": "draft",
                }
            )
            # Store mapping by BPMN id
            if elem_id:
                task_map[elem_id] = task
            sequence += 10

        # Phase 2: Create connections (sequence flows)
        seq = 0
        for child in process:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag != "sequenceFlow":
                continue

            source_ref = child.get("sourceRef", "")
            target_ref = child.get("targetRef", "")
            flow_name = child.get("name", "")

            source_task = task_map.get(source_ref)
            target_task = task_map.get(target_ref)

            if source_task and target_task:
                self.env["bpm.task.decision"].create(
                    {
                        "bpm_id": self.id,
                        "parent_id": source_task.id,
                        "child_id": target_task.id,
                        "option": flow_name,
                        "sequence": seq,
                    }
                )
                seq += 10

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("BPMN Import Complete"),
                "message": _("Imported %d tasks and %d connections.") % (
                    len(task_map),
                    seq // 10,
                ),
                "type": "success",
            },
        }


class BPMNImportWizard(models.TransientModel):
    """Wizard for importing BPMN 2.0 XML into an existing workflow."""

    _name = "bpm.bpmn.import.wizard"
    _description = "BPMN 2.0 Import Wizard"

    workflow_id = fields.Many2one(
        "bpm.workflow", string="Workflow", required=True, readonly=True
    )
    bpmn_file = fields.Binary(string="BPMN 2.0 XML File", required=True)
    filename = fields.Char(string="Filename")

    def action_import(self):
        """Read uploaded file and import into workflow."""
        self.ensure_one()
        if not self.bpmn_file:
            raise UserError(_("Please upload a BPMN 2.0 XML file."))

        xml_content = self.bpmn_file
        if isinstance(xml_content, bytes):
            xml_content = xml_content.decode("utf-8")

        return self.workflow_id.import_bpmn(xml_content)
