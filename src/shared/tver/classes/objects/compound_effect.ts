import { PropertyNames } from "shared/tver/utility/_ts_only/types"
import { CustomPropertyEffect, StrictPropertyEffect } from "../fundamental/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../fundamental/stat_effect"
import { JumpHeightEffect, WalkSpeedEffect } from "shared/tver/test/stat_effect_classes";
import { AutoRotateEffect } from "shared/tver/test/property_effect_classes";


export abstract class CompoundEffect {
    public abstract readonly duration: number;

    public abstract readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[]
    public abstract readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[]

    constructor () {}
}

export class Stun extends CompoundEffect {
    public readonly duration: number;

    public readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[];
    public readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[];

    constructor (_duration: number) {
        super()
        this.duration = _duration

        this.PropertyEffects = [
            new AutoRotateEffect(false, this.duration)
        ]
        this.StatEffects = [
            new WalkSpeedEffect("Modifer", 0, this.duration),
            new JumpHeightEffect("Modifer", 0, this.duration)
        ]
    }
}