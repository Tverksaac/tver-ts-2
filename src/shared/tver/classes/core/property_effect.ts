import { Affects, Strength } from "shared/tver/utility/_ts_only/types"
import { Effect } from "./effect"

/**
 * Base for effects that set a property value, optionally with priority.
 */
abstract class PropertyEffect extends Effect {
    public abstract Priority?: number

    /** Set priority; higher wins when combining property effects. */
    public SetPriority(new_priority: number): void {
        this.Priority = new_priority
    }
}

/**
 * Property effect that targets a concrete instance property by name.
 */
export abstract class StrictPropertyEffect<ConnectedInstance extends Instance, Name extends Affects<ConnectedInstance>> extends PropertyEffect {
    public readonly Affects!: Affects<ConnectedInstance>

    public abstract readonly Strength: Strength<ConnectedInstance, Name>
    public readonly Priority?: number
}

/**
 * Property effect that targets a custom property identified by string key.
 */
export abstract class CustomPropertyEffect extends PropertyEffect{
    public readonly Affects: string
    
    public abstract readonly Strength: defined;
    public abstract readonly Priority?: number

    constructor (affects: string) {
        super()
        this.Affects = affects
    }
}