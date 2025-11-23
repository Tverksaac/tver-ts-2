import { StrictPropertyEffect } from "../classes/core/property_effect";

export class AutoRotateEffect extends StrictPropertyEffect<Humanoid, "AutoRotate"> {
	public readonly Affects = "AutoRotate";
	public readonly Strength: boolean;
	public readonly Priority?: number | undefined;

	constructor(_str: boolean, pr: number) {
		super();

		this.Strength = _str;
		this.Priority = pr;
	}
}
