import { StrictStatEffect } from "../classes/fundamental/stat_effect";

export class WalkSpeedEffect extends StrictStatEffect<Humanoid> {
    public readonly duration: number;
    public readonly strength: number;
    public readonly effect_type: "Raw" | "Modifer";

    constructor (_type: "Raw" | "Modifer", _str: number, _dur: number) {
        super("WalkSpeed")

        this.duration = _dur
        this.effect_type = _type
        this.strength = _str
    }
}
export class JumpHeightEffect extends StrictStatEffect<Humanoid> {
    public readonly duration: number;
    public readonly strength: number;
    public readonly effect_type: "Raw" | "Modifer";

    constructor (_type: "Raw" | "Modifer", _str: number, _dur: number) {
        super("JumpHeight")

        this.duration = _dur
        this.effect_type = _type
        this.strength = _str
    }
}