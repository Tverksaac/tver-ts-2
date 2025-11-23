import { AppliedCompoundEffect, CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { JumpHeightEffect, WalkSpeedEffect } from "./stat_effect_classes";
import { AutoRotateEffect } from "./property_effect_classes";
import { CompoundEffectPropertyEffects, CompoundEffectStatEffects } from "../utility/_ts_only/types";
import { Character } from "../exports";

class AppliedStun extends AppliedCompoundEffect<{
	ConstructorParams: [AutoRotate: boolean];
}> {
	public auto: boolean = this.InheritsFrom.ConstructorParams[0];
	public counter = 0;

	public OnStartServer(): void {
		this.counter++;
		print(this.counter);
	}
}
@Decorator_CompoundEffect
export class Stun extends CompoundEffect<{
	ConstructorParams: [AutoRotate: boolean];
}> {
	public PropertyEffects: CompoundEffectPropertyEffects;
	public StatEffects: CompoundEffectStatEffects;

	constructor(AutoRotate: boolean) {
		super(AutoRotate);
		this.StatEffects = [new JumpHeightEffect("Modifier", 0), new WalkSpeedEffect("Modifier", 0)];
		this.PropertyEffects = [new AutoRotateEffect(AutoRotate || false, 999)];
	}

	public ApplyTo(
		to: Character,
		duration: number,
	): AppliedCompoundEffect<{ ConstructorParams: [AutoRotate?: boolean] }> {
		return new AppliedStun(this, to, duration);
	}
}
