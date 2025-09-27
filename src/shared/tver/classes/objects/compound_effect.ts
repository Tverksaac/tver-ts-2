import { CustomPropertyEffect, StrictPropertyEffect } from "../fundamental/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../fundamental/stat_effect"
import { Character } from "./character";

export abstract class CompoundEffect {
    public readonly name: string
    public abstract readonly duration: number;

    public abstract readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[]
    public abstract readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[]

    constructor (_name: string) {
        this.name = _name
    }

    public ApplyTo(to: Character) {
        return new AppliedCompoundEffect(this, to)
    }
}

export class AppliedCompoundEffect extends CompoundEffect{
    public duration: number;
    public StatEffects: (StrictStatEffect<never> | CustomStatEffect)[];
    public PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[];

    public readonly InheritsFrom: CompoundEffect
    public readonly CarrierID: number

    constructor (from: CompoundEffect, to: Character) {
        super(from.name)
        this.InheritsFrom = from
        this.CarrierID = to.id

        this.duration = from.duration
        this.StatEffects = from.StatEffects
        this.PropertyEffects = from.PropertyEffects
    }

    public Start() {}
    public Resume() {}
    public Stop() {}
    public End() {}
}