import { CompoundEffect, Decorator_CompoundEffect } from "../classes/objects/compound_effect";
import { JumpHeightEffect, WalkSpeedEffect } from "./stat_effect_classes";
import { AutoRotateEffect } from "./property_effect_classes";
import { CompoundEffectPropertyEffects, CompoundEffectStatEffects, Strength } from "../utility/_ts_only/types";

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

	public OnStartServer(): void {
		print("not overrided");
	}
	public OnStartClient(): void {
		print("started on cleint");
	}
}
