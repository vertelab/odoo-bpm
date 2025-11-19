/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal/chatter";

patch(Chatter.prototype, {
    async onClickShowBPMTasks() {
        if (this.isTemporary) {
            const saved = await this.doSaveRecord();
            if (!saved) {
                return;
            }
        }

        const record = this.props.webRecord;

        let bpmTaskIds = [];
        if (record.data.bpm_task_ids) {
            if (Array.isArray(record.data.bpm_task_ids)) {
                bpmTaskIds = record.data.bpm_task_ids;
            } else if (record.data.bpm_task_ids.records) {
                bpmTaskIds = record.data.bpm_task_ids.records.map(r => r.resId);
            }
        }

        // Load the action
        const action = await this.env.services.action.loadAction(
            "bpm_workflow.open_bpm_tasks_thread_kanban"
        );

        // Override domain with the filtered IDs
        action.domain = [['id', 'in', bpmTaskIds]];
        action.context = {
            bpm_task_ids: bpmTaskIds,
        };

        // Execute the action with modified domain
        this.env.services.action.doAction(action);
    }
})