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

    public Start() {

        this._state = "On"
    }
    public Resume() {

        this._state = "On"
    }
    public Stop() {

        this._state = "Off"
    }
    public End() {

        this._state = "Ended"
    }

    public GetState() {
        return this._state
    }
}