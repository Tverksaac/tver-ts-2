import { AppliedCompoundEffect } from "./exports";
import { Character } from "./classes/objects/character";
import { ClientEvents } from "./network/networking";
import { CompoundEffectInfo } from "./utility/_ts_only/interfaces";
import { get_logger } from "./utility/utils";

const LOG_KEY = "[MANIPULATOR]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

function sync_compound_effect(info: CompoundEffectInfo): void {
    if (info.state === "Ready") return // No need to replciate Ready status
    const warn_msg = "Failed to sync compound effect with id: " + info.id

    const char = Character.GetCharacterFromId(1) // Local id = 1
    if (!char) {
        log.w(warn_msg + " Client-Sided Character was not found")
    }
    const effect = char?.AwaitForCompoundEffect(info.id) as AppliedCompoundEffect<{ OnStart: unknown[], OnResume: unknown[], OnPause: unknown[] }> // Client-sided
    
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
}

export class Manipulator {
    public client_initialize(): boolean {
        ClientEvents.Manipulate.sync_compound_effect.connect(sync_compound_effect)
        return true
    }
    public server_initialize(): boolean {
        return true
    }
}

/**
 * Client-Context
 */


