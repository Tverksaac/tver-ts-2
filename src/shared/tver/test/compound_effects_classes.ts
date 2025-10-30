import { CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { AutoRotateEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";

@Decorator_CompoundEffect
export class Stun extends CompoundEffect {

    public StartOnApply: boolean = true
    public PropertyEffects = [
        new AutoRotateEffect(false, 10)
    ]
    public StatEffects = [
        new WalkSpeedEffect("Modifer", 0),
        new JumpHeightEffect("Modifer", 0)
    ]
}