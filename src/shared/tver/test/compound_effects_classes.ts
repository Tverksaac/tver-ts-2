
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

    public ApplyTo(to: Character, duration?: number, id?: number): AppliedCompoundEffect<{ ConstructorParams: [strength: number]; }> {
        const applied = new AppliedCompoundEffect(this, to, duration || -1)

        applied.OnStartServer = () => {
        let counter = 1
        while (true) {
            counter++
            print(counter)
            if (counter === 10) {
                applied._resume_thread? coroutine.close(applied._resume_thread): undefined
            }
            print("mmm it shoudnt loged")
     }
        }

        return applied
    }
}
