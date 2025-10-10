import { Effect } from "../core/effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../core/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../core/stat_effect"
import { Character } from "./character";
import { EffectState } from "shared/tver/utility/_ts_only/types";
import { StateMachine } from "../fundamental/state_machine";
import { get_id, is_client_context, wlog } from "shared/tver/utility/utils";

function throw_client_warn(): boolean {
    if (is_client_context()) {
        wlog("Cant manipulate status effect on client!")
        return true
    }
    return false
}

export abstract class CompoundEffect {
    public readonly Name: string
    public abstract readonly Duration: number;

    public abstract readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[]
    public abstract readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[]

    constructor (_name: string) {
        this.Name = _name
    }

    public ApplyTo(to: Character) {
        return new AppliedCompoundEffect(this, to)
    }
}


export class AppliedCompoundEffect extends CompoundEffect{
    public Duration: number;
    public StatEffects: (StrictStatEffect<never> | CustomStatEffect)[];
    public PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[];

    public readonly state = new StateMachine<[EffectState]>()
    public readonly id = get_id()

    public readonly InheritsFrom: CompoundEffect
    public readonly CarrierID: number

    constructor (from: CompoundEffect, to: Character) {
        super(from.Name)
        this.InheritsFrom = from
        this.CarrierID = to.id

        this.Duration = from.Duration
        this.StatEffects = from.StatEffects
        this.PropertyEffects = from.PropertyEffects

        this.ApplyTo = () => {
            wlog("Cant call :ApplyTo on AppliedStatusEffect!")
            return this
        }

        this.state.SetState("Ready")
        this.Start()

        to._internal_apply_effect(this)
    }

    public for_each_effect(callback: (effect: Effect) => void) {
        this.StatEffects.forEach(callback)
        this.PropertyEffects.forEach(callback)
    }

    public Start() {
        if (throw_client_warn()) return
        if (this.state.GetState() !== "Ready") {
            warn(this + " Effect cant be started twice!")
            return
        }

        this.state.SetState("On")

        this.for_each_effect((effect) => {
            effect.Start()
        })
    }
    public Resume() {
    if (throw_client_warn()) return
        if (this.state.GetState() === "Ended") {
            warn(this + " is already ended!")
            return
        }

        this.state.SetState("On")

        this.for_each_effect((effect) => {
            effect.Resume()
        })
    }
    public Stop() {
        if (throw_client_warn()) return
        if (this.state.GetState() === "Ended") {
            warn(this + " is already ended!")
            return
        }

        this.state.SetState("Off")

        this.for_each_effect((effect) => {
            effect.Stop()
        })
    }
    public End() {
        if (throw_client_warn()) return
        if (this.state.GetState() === "Ended") {
            warn(this + " is already ended!")
            return
        }

        this.state.SetState("Ended")

        this.for_each_effect((effect) => {
            effect.End()
        })

        const carrier = Character.GetCharacterFromId(this.CarrierID)
        carrier?._internal_remove_effect(this.id)

        this.Destroy()
    }
    public Destroy() {
        if (throw_client_warn()) return

        if (this.state.GetState() !== "Ended") {this.End()}

        this.for_each_effect((effect) => {
            effect.Destroy()
        })
    }
}