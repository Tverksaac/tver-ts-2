import { StrictStatEffect } from "../classes/fundamental/stat_effect";

export class JumpHeightEffect extends StrictStatEffect<Humanoid> {
    public readonly Duration: number;
    public readonly Strength: number;
    public readonly EffectType: "Raw" | "Modifer";

    constructor (_type: "Raw" | "Modifer", _str: number, _dur: number) {
        super("WalkSpeed")

        this.Duration = _dur
        this.EffectType = _type
        this.Strength = _str
    }
}