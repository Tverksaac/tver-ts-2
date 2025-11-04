import { Workspace } from "@rbxts/services";
import { AppliedCompoundEffect, CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { AutoRotateEffect, TestEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";

@Decorator_CompoundEffect
export class Stun extends CompoundEffect<
    {
        OnStart: [ignore: boolean | undefined]
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
    public OnStartServer(ignore: boolean): void {
        this.applied_effect.ExtendDuration(10)
        print('extended by 10')
    }
}
