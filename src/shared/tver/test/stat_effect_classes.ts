import { StrictStatEffect } from "../classes/core/stat_effect";
import { EffectType } from "../utility/_ts_only/types";

export class JumpHeightEffect extends StrictStatEffect<Humanoid> {
	public readonly Affects = "JumpHeight" as const;
	public readonly Strength: number;
	public readonly EffectType: EffectType;

	constructor(_type: EffectType, _str: number) {
		super();

		this.EffectType = _type;
		this.Strength = _str;
	}
}
export class WalkSpeedEffect extends StrictStatEffect<Humanoid> {
	public readonly Affects = "WalkSpeed" as const;
	public readonly Strength: number;
	public readonly EffectType: EffectType;

	constructor(_type: EffectType, _str: number) {
		super();

		this.EffectType = _type;
		this.Strength = _str;
	}
}
