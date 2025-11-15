import { AppliedCompoundEffect, Character, Client } from "./exports";
import { ClientEvents, ServerEvents } from "./network/networking";
import { EffectState } from "./utility/_ts_only/types";
import { get_logger } from "./utility/utils";

const LOG_KEY = "[MANIPULATOR]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

export const _manipulator = {}

/**
 * Client-Context
 */
ClientEvents.Manipulate.sync_compound_effect.connect((info) => {
    const warn_msg = "Failed to sync compound effect with id: " + info.id

    const char = Character.GetCharacterFromId(1) // Local id = 1
    const effect = char?.GetAppliedEffectFromId(info.id) as AppliedCompoundEffect<{OnStart: unknown[], OnResume: unknown[], OnPause: unknown[]}> // Client-sided

    if (!effect) {
        log.w(warn_msg + " Failed to find from id.")
        return
    }

    const state = info.state

    if (state === "On") {
        if (effect.state.GetState() === "Ready") effect.Start(info.start_params)
        else if (effect.state.GetState() === "Off") effect.Resume(info.resume_params)
    } else if (state === "Off") {
        effect.Pause(info.pause_params)
    } else {
        log.w(warn_msg + " Failed to determine manipulation action")
        return
    }
})