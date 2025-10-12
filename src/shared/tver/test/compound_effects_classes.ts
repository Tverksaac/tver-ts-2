import { CustomPropertyEffect, StrictPropertyEffect } from "../classes/core/property_effect";
import { CustomStatEffect, StrictStatEffect } from "../classes/core/stat_effect";
import { AppliedCompoundEffect, CompoundEffect, CompoundEffectDecorator, CompoundEffectsContainer } from "../classes/objects/compound_effect";
import { Character } from "../exports";
import { AutoRotateEffect } from "./property_effect_classes";
import { JumpHeightEffect} from "./stat_effect_classes";

@CompoundEffectDecorator
export class Stun extends CompoundEffect {
    public readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[];
    public readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[];

    constructor () {
        super("Stun")

        this.PropertyEffects = [
            new AutoRotateEffect(false)
        ]
        this.StatEffects = [
            new JumpHeightEffect("Modifer", 0)
        ]
    }
}