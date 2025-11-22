import { Decorator_Skill, Skill } from "../exports";

@Decorator_Skill
export class Punch extends Skill {
	public OnRecieveClient(recieved_skill: Skill<{}>): void {}
}
