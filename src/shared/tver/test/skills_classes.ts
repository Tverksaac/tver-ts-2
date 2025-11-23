import { AppliedCompoundEffect, AppliedSkill, Decorator_Skill, Skill } from "../exports";

@Decorator_Skill
export class Punch extends Skill<{
	ConstructorParams: [damage: number];
}> {
	constructor(damage: number) {
		super(damage);
	}
	public OnRecieveServer(recieved_skill: AppliedSkill<{ ConstructorParams: [damage: number] }>): void {
		print();
	}
}
