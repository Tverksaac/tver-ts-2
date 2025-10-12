import { StrictStatEffect } from "../classes/core/stat_effect";

export class JumpHeightEffect extends StrictStatEffect<Humanoid> {
    public readonly Strength: number;
    public readonly EffectType: "Raw" | "Modifer";

    constructor (_type: "Raw" | "Modifer", _str: number) {
        super("WalkSpeed")

        this.EffectType = _type
        this.Strength = _str
    }
}