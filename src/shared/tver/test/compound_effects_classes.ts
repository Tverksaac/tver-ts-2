import { CustomPropertyEffect, StrictPropertyEffect } from "../classes/fundamental/property_effect";
import { CustomStatEffect, StrictStatEffect } from "../classes/fundamental/stat_effect";
import { CompoundEffect } from "../classes/objects/compound_effect";
import { AutoRotateEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect } from "./stat_effect_classes";

export class Stun extends CompoundEffect {
    public readonly duration: number;

    public readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[];
    public readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[];

    constructor (_duration: number) {
        super("Stun")
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