/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal/chatter";

patch(Chatter.prototype, {
    async onClickShowNonConformities() {

        const saved = await this.props.saveRecord?.();
        if (!saved) {
            return;
        }

        this.env.services.action.doAction(
            "bpm_workflow.action_bpm_workflow",
            {
                additionalContext: {
                    id: this.state.thread.id,
                    mgmtsystem_nonconformity: this.state.thread.model,
                },
            }
        );
    }
})
