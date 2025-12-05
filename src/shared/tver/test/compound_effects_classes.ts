import { CompoundEffect, Decorator_CompoundEffect, LinkedCompoundEffect } from "../classes/objects/compound_effect";
import { JumpHeightEffect, WalkSpeedEffect } from "./stat_effect_classes";
import { AutoRotateEffect } from "./property_effect_classes";
import { CompoundEffectPropertyEffects, CompoundEffectStatEffects, Strength } from "../utility/_ts_only/types";
import { Character } from "../exports";

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
}

@Decorator_CompoundEffect
export class Test extends LinkedCompoundEffect<{}> {
	public sigma: number = 2;
	public StatEffects: CompoundEffectStatEffects = [new WalkSpeedEffect("Modifier", 2)];

	constructor(link_to: Character) {
		super(link_to);
		this.sigma = 1;
		print(this.sigma);
	}

	public OnStartServer(this: CompoundEffect<{}>): void {
		print(this);
	}
	public OnStartClient(this: CompoundEffect<{}>): void {
		print(this);
	}
}
