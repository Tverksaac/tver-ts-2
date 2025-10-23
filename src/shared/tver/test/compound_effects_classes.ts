import { CustomPropertyEffect, StrictPropertyEffect } from "../classes/core/property_effect";
import { CustomStatEffect, StrictStatEffect } from "../classes/core/stat_effect";
import { AppliedCompoundEffect, CompoundEffect, CompoundEffectDecorator } from "../classes/objects/compound_effect";
import { Character } from "../exports";
import { AutoRotateEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";

@CompoundEffectDecorator
export class Stun extends CompoundEffect {
    public StartOnApply: boolean = false
    public PropertyEffects = [
        new AutoRotateEffect(false, 10)
    ]
    public StatEffects = [
        new WalkSpeedEffect("Modifer", 0),
        new JumpHeightEffect("Modifer", 0)
    ]

    protected OnStartServer(): void {
        print("Stun started on server!")
    }
    protected OnStartClient(): void {
        print("Stun started on client!")
    }
}