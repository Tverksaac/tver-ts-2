import { get_logger } from "shared/tver/utility/utils";
import { Character } from "./character";
import { Constructor } from "@flamework/core/out/utility";
import { GetParamType, SkillGenericParams, SkillState } from "shared/tver/utility/_ts_only/types";
import { StateMachine } from "../fundamental/state_machine";
import { Janitor } from "@rbxts/janitor";
import { Timer } from "../fundamental/timer";

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

/**
 * Unique for every character
 */
export abstract class Skill<Params extends Partial<SkillGenericParams> = {}> {
	public readonly Name = tostring(getmetatable(this));
	public readonly ConstructorParams: GetParamType<Params, "ConstructorParams">;
	public readonly Carrier: Character;

	public readonly state = new StateMachine<[SkillState]>("Ready");
	public readonly janitor = new Janitor();

	constructor(Carrier: Character, ...params: GetParamType<Params, "ConstructorParams">);
	constructor(Carrier: Character, ...params: GetParamType<Params, "ConstructorParams">) {
		this.Carrier = Carrier;
		this.ConstructorParams = params;
	}

	//@override
	public OnRecieveServer() {}
	public OnRecieveClient() {}
	public OnStartServer(...params: GetParamType<Params, "OnStart">) {}
	public OnStartClient(...params: GetParamType<Params, "OnStart">) {}
	public OnAbortServer(...params: GetParamType<Params, "OnAbort">) {}
	public OnAbortClient(...params: GetParamType<Params, "OnAbort">) {}
	public OnRemoveServer(...params: GetParamType<Params, "OnRemove">) {}
	public OnRemoveClient(...params: GetParamType<Params, "OnRemove">) {}
	public OnEndServer() {}
	public OnEndClient() {}

	public Start() {}
	public Abort() {}
	public End() {}
	public Remove() {}

	public Destroy(): void {}

	private init() {}
}

export function Decorator_Skill<Params extends Partial<SkillGenericParams>>(
	Constructor: Constructor<Skill<Params>>,
): void {
	Container_Skill.Register(Constructor);
}
