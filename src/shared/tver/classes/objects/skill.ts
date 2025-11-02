import { get_logger } from "shared/tver/utility/utils";
import { Character } from "./character";
import { Constructor } from "@flamework/core/out/utility";

const LOG_KEY = "[SKILL]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

class Container_Skill {
    public static readonly RegisteredSkills = new Map<string, Skill>()

    /**
     * Register a `Skill` class by constructor.
     */
    public static Register<T extends Skill>(Skill: Constructor<T>) {
        const name = tostring(Skill)
        if (this.RegisteredSkills.has(name)) {log.w(Skill + " already registered"); return}
        this.RegisteredSkills.set(name, new Skill())
    }
    /**
     * Get a registered skill instance by its name.
     */
    public static GetFromName(name: string): Skill | undefined {
        return this.RegisteredSkills.get(name)
    }
    /**
     * Get a registered skill instance by its constructor.
     */
    public static GetFromConstructor<T extends Skill>(Constructor: Constructor<T>): T | undefined {
        return this.RegisteredSkills.get(tostring(Constructor)) as T
    }
}

export abstract class Skill {

    public readonly Name = tostring(getmetatable(this))

    //@override
    public OnRecieveServer() {}
    public OnRecieveClient() {}
    public OnStartServer() {}
    public OnStartClient() {}
    public OnAbortServer() {}
    public OnAbortClient() {}
    public OnEndServer() {}
    public OnEndClient() {}
    public OnRemoveServer() {}
    public OnRemoveClient() {}

    public GiveTo(to: Character): AppliedSkill {
        return new AppliedSkill(this, to)
    }
}
export class AppliedSkill extends Skill {

    public InheritsFrom: Skill;
    public Carrier: Character;

    constructor (from: Skill, to: Character) {
        super()

        this.InheritsFrom = from
        this.Carrier = to

        this.GiveTo = () => {
            return this
        }
    }

    public Remove(): void {

    }

    public init() {

    }
}