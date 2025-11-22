import { CustomPropertyEffect, StrictPropertyEffect } from "../classes/core/property_effect";

export class AutoRotateEffect extends StrictPropertyEffect<Humanoid, "AutoRotate"> {
	public readonly Affects = "AutoRotate" as const;
	public readonly Strength: boolean;
	public readonly Priority?: number | undefined;

	constructor(_str: boolean, pr: number) {
		super();

		this.Strength = _str;
		this.Priority = pr;
	}
}

export class TestEffect extends CustomPropertyEffect {
	public Affects: string = "Test";
	public Strength = 1;
	public Priority?: number | undefined = 1;
}
