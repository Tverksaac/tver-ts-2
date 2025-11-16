
import { AppliedCompoundEffect, CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { AutoRotateEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";
import { Character, CustomStatEffect, StrictStatEffect } from "../exports";

@Decorator_CompoundEffect
export class JumpBoost extends CompoundEffect<
    {
        ConstructorParams: [strength: number]
    }
> {
    public StatEffects: (StrictStatEffect<Humanoid> | CustomStatEffect)[];
    
    constructor (strength: number) {
        super(strength)
        this.StatEffects = [
            new JumpHeightEffect("Raw", strength)
        ]
    }

    public OnStartServer(): void {
        
    }
}
