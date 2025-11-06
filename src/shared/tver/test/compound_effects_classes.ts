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
}

@Decorator_CompoundEffect
export class SpeedBoost extends CompoundEffect<{
    ConstructorParams: [strength: number]
}> {
    public StatEffects: (StrictStatEffect<never> | CustomStatEffect)[]

    private _applied!: AppliedCompoundEffect

    constructor (strength: number) {
        super([strength])
        this.StatEffects = [
            new WalkSpeedEffect("Modifier", strength)
        ]
    }

    public OnApplyingServer(applied: AppliedCompoundEffect<{ ConstructorParams: [strength: number]; }>): void {
        this._applied = applied
    }

    public OnEndServer(): void {
        const constructor = Container_CompoundEffect.GetFromConstructor(Stun)
        const effect = constructor? new constructor([]): undefined

        effect?.ApplyTo(this._applied.Carrier, 3).Start()
    }
}
