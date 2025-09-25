import { CustomPropertyEffect, StrictPropertyEffect } from "../fundamental/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../fundamental/stat_effect"

export abstract class CompoundEffect {
    public abstract readonly duration: number;

    public abstract readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[]
    public abstract readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[]

    constructor () {}
}