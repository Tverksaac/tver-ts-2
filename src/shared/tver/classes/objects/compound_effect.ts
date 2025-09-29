import { Effect } from "../fundamental/effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../fundamental/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../fundamental/stat_effect"
import { Character } from "./character";
import { EffectState } from "shared/tver/utility/_ts_only/types";
import { StateMachine } from "../fundamental/state_machine";

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

    public readonly InheritsFrom: CompoundEffect
    public readonly CarrierID: number

    constructor (from: CompoundEffect, to: Character) {
        super(from.Name)
        this.InheritsFrom = from
        this.CarrierID = to.id

        this.Duration = from.Duration
        this.StatEffects = from.StatEffects
        this.PropertyEffects = from.PropertyEffects
    }

    private for_each_effect(callback: (effect: Effect) => void) {
        this.StatEffects.forEach(callback)
        this.PropertyEffects.forEach(callback)
    }

    public Start() {
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
        if (this.state.GetState() === "Ended") {
            warn(this + " is already ended!")
            return
        }

        this.state.SetState("Ended")

        this.for_each_effect((effect) => {
            effect.End()
        })
    }
}