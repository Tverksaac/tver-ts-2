import { CustomPropertyEffect, StrictPropertyEffect } from "../classes/core/property_effect";
import { CustomStatEffect, StrictStatEffect } from "../classes/core/stat_effect";
import { AppliedCompoundEffect, CompoundEffect, CompoundEffectDecorator, CompoundEffectsContainer } from "../classes/objects/compound_effect";
import { Character } from "../exports";
import { AutoRotateEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";

@CompoundEffectDecorator
export class Stun extends CompoundEffect {
    public readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[];
    public readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[];

    constructor () {
        super("Stun")

        this.PropertyEffects = [
            new AutoRotateEffect(false, 1),
            new AutoRotateEffect(true, 2)
        ]
        this.StatEffects = [
            new JumpHeightEffect("Modifer", 0),
            new WalkSpeedEffect("Modifer", 0)
        ]
    }
}