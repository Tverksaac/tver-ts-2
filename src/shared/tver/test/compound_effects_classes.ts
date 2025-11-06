import { Workspace } from "@rbxts/services";
import { AppliedCompoundEffect, CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { AutoRotateEffect, TestEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";
import { StrictPropertyEffect, CustomPropertyEffect, CustomStatEffect, StrictStatEffect } from "../exports";

@Decorator_CompoundEffect
export class Stun extends CompoundEffect<
    {
        OnStart: [ignore: boolean | undefined],
        OnResume: [time: number]
    }
> {
    public PropertyEffects = [
        new AutoRotateEffect(false, 10),
    ]
    public StatEffects = [
        new WalkSpeedEffect("Modifier", 0),
        new JumpHeightEffect("Modifier", 0),
    ]

    private applied_effect!: AppliedCompoundEffect

    public OnApplyingServer(applied: AppliedCompoundEffect<{ OnStart: [ignore: boolean]; }>): void {
        this.applied_effect = applied
    }
}
export class SpeedBoost extends CompoundEffect<{
    ConstructorParams: [strength: number]
}> {
    public StatEffects: (StrictStatEffect<never> | CustomStatEffect)[]

    constructor (strength: number) {
        super([strength])
        this.StatEffects = [
            new WalkSpeedEffect("Modifier", strength)
        ]
    }
}
