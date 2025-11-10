
import { AppliedCompoundEffect, CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { AutoRotateEffect } from "./property_effect_classes";
import { JumpHeightEffect, WalkSpeedEffect} from "./stat_effect_classes";
import { Character, CustomStatEffect, StrictStatEffect } from "../exports";

@Decorator_CompoundEffect
export class Stun extends CompoundEffect<{}> {
    public PropertyEffects = [
        new AutoRotateEffect(false, 10),
    ]
    public StatEffects = [
        new WalkSpeedEffect("Modifier", 0),
        new JumpHeightEffect("Modifier", 0),
    ]

    public ApplyTo(to: Character): AppliedCompoundEffect {
        const effect = new AppliedCompoundEffect(this, to, 5)

        effect.OnStartServer = () => {
            print("Overrided effect!")
        }
        effect.Start()
        return effect
    }
    public OnApplyingServer(applied: AppliedCompoundEffect): void {

    }
    public OnStartServer(): void {
        print("Not overrided")
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

    public OnStartServer(): void {
        
    }
}
