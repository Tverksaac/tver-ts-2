import { effect } from "@rbxts/charm";
import { Effect } from "../fundamental/effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../fundamental/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../fundamental/stat_effect"
import { Character } from "./character";

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

    private _state: "Ready" | "On" | "Off" | "Ended"

    public readonly InheritsFrom: CompoundEffect
    public readonly CarrierID: number

    constructor (from: CompoundEffect, to: Character) {
        super(from.Name)
        this.InheritsFrom = from
        this.CarrierID = to.id

        this.Duration = from.Duration
        this.StatEffects = from.StatEffects
        this.PropertyEffects = from.PropertyEffects
        
        this._state = "Ready"
    }

    private for_each_effect(callback: (effect: Effect) => void) {
        this.StatEffects.forEach(callback)
        this.PropertyEffects.forEach(callback)
    }

    public Start() {
        if (this._state !== "Ready") {
            warn(this + " Effect cant be started twice!")
            return
        }

        this._state = "On"

        this.for_each_effect((effect) => {
            effect.Start()
        })
    }
    public Resume() {
        if (this._state === "Ended") {
            warn(this + " is already ended!")
            return
        }

        this._state = "On"

        this.for_each_effect((effect) => {
            effect.Resume()
        })
    }
    public Stop() {
        if (this._state === "Ended") {
            warn(this + " is already ended!")
            return
        }

        this._state = "Off"

        this.for_each_effect((effect) => {
            effect.Stop()
        })
    }
    public End() {
        if (this._state === "Ended") {
            warn(this + " is already ended!")
            return
        }

        this._state = "Ended"

        this.for_each_effect((effect) => {
            effect.End()
        })
    }

    public GetState() {
        return this._state
    }
}