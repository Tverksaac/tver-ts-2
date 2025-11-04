import { CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { AutoRotateEffect, TestEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";

@Decorator_CompoundEffect
export class Stun extends CompoundEffect<
    {
        OnStart: [ignore: boolean]
    }
> {
    
    public PropertyEffects = [
        new AutoRotateEffect(false, 10),
        new TestEffect()
    ]
    public StatEffects = [
        new WalkSpeedEffect("Modifier", 0),
        new JumpHeightEffect("Modifier", 0),
    ]

    public OnStartServer(ignore: boolean): void {}
}
