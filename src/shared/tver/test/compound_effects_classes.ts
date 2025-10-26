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

    public OnStartServer(): void {
        print("Stun started on server!")
    }
    public OnStartClient(): void {
        print("Stun started on client!")
    }
    public OnEndServer(): void {
        print("Stun ended on server!")
    }
    public OnEndClient(): void {
        print("Stun ended on client!")
    }
    public OnPauseServer(): void {
        print("paused")
    }
    public OnResumeServer(): void {
        print("resumed")
    }
}