import { Workspace } from "@rbxts/services";
import { AppliedCompoundEffect, CompoundEffect, Container_CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { AutoRotateEffect, TestEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";
import { StrictPropertyEffect, CustomPropertyEffect, CustomStatEffect, StrictStatEffect } from "../exports";

@Decorator_CompoundEffect
export class Stun extends CompoundEffect<
    {
        ConstructorParams: undefined
    }
> {
    public PropertyEffects = [
        new AutoRotateEffect(false, 10),
    ]
    public StatEffects = [
        new WalkSpeedEffect("Modifier", 0),
        new JumpHeightEffect("Modifier", 0),
    ]

    public OnApplyingServer(applied: AppliedCompoundEffect<{ ConstructorParams: undefined; }>): void {
        
    }
}

@Decorator_CompoundEffect
export class JumpBoost extends CompoundEffect<
    {
        ConstructorParams: [strength: number]
    }
> {
    public StatEffects: (StrictStatEffect<never> | CustomStatEffect)[];
    

    constructor (strength: number) {
        super([strength])
        this.StatEffects = [
            new JumpHeightEffect("Raw", strength)
        ]
    }
}
