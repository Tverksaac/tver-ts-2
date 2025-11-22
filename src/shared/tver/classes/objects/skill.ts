import { get_logger } from "shared/tver/utility/utils";
import { Character } from "./character";
import { Constructor } from "@flamework/core/out/utility";
import { GetParamType, SkillGenericParams } from "shared/tver/utility/_ts_only/types";

const LOG_KEY = "[SKILL]";
const log = get_logger(LOG_KEY);
const dlog = get_logger(LOG_KEY, true);

export class Container_Skill {
	public static readonly RegisteredSkills = new Map<string, Constructor<Skill>>();

	/**
	 * Register a `Skill` class by constructor.
	 */
	public static Register<T extends Constructor<Skill>>(Skill: T) {
		const name = tostring(Skill);
		if (this.RegisteredSkills.has(name)) {
			log.w(Skill + " already registered");
			return;
		}
		this.RegisteredSkills.set(name, Skill);
	}
	/**
	 * Get a registered skill instance by its name.
	 */
	public static GetFromName(name: string): Constructor<Skill> | undefined {
		return this.RegisteredSkills.get(name);
	}
	/**
	 * Get a registered skill instance by its constructor.
	 */
	public static GetFromConstructor<T extends Constructor<Skill>>(Constructor: T): T | undefined {
		return this.RegisteredSkills.get(tostring(Constructor)) as T;
	}
}

export abstract class Skill<Params extends Partial<SkillGenericParams> = {}> {
	public readonly Name = tostring(getmetatable(this));

	//@override
	public OnRecieveServer(recieved_skill: AppliedSkill<Params>) {}
	public OnRecieveClient(recieved_skill: AppliedSkill<Params>) {}
	public OnStartServer(...params: GetParamType<Params, "OnStart">) {}
	public OnStartClient(...params: GetParamType<Params, "OnStart">) {}
	public OnAbortServer(...params: GetParamType<Params, "OnAbort">) {}
	public OnAbortClient(...params: GetParamType<Params, "OnAbort">) {}
	public OnRemoveServer(...params: GetParamType<Params, "OnRemove">) {}
	public OnRemoveClient(...params: GetParamType<Params, "OnRemove">) {}
	public OnEndServer() {}
	public OnEndClient() {}
	public GiveTo(to: Character): AppliedSkill {
		return new AppliedSkill(this, to);
	}
}
export class AppliedSkill<Params extends Partial<SkillGenericParams> = {}> extends Skill<Params> {
	public InheritsFrom: Skill;
	public Carrier: Character;

	constructor(from: Skill, to: Character) {
		super();

		this.InheritsFrom = from;
		this.Carrier = to;

		this.GiveTo = () => {
			log.w("Can't give an already Applied Skill!");
			return this;
		};
	}

	public Remove(): void {}

	private init() {}
}

export function Decorator_Skill<Params extends Partial<SkillGenericParams>>(
	Constructor: Constructor<Skill<Params>>,
): void {
	Container_Skill.Register(Constructor);
}
