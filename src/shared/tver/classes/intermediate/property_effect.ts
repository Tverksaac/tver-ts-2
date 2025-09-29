import { SoundService } from "@rbxts/services"
import { Timer } from "@rbxts/timer"
import { Affects, Strength } from "shared/tver/utility/_ts_only/types"
import { Effect } from "./effect"

abstract class PropertyEffect extends Effect {
    public abstract Priority?: number

    public SetPriority(new_priority: number) {
        this.Priority = new_priority
    }
}

export abstract class StrictPropertyEffect<ConnectedInstance extends Instance, Name extends Affects<ConnectedInstance>> extends PropertyEffect {
    public readonly Affects: Affects<ConnectedInstance>

    public abstract readonly Duration: number
    public abstract readonly Strength: Strength<ConnectedInstance, Name>
    public readonly Priority?: number

    constructor (affects: Affects<ConnectedInstance>) {
        super()
        this.Affects = affects
    }
}

export abstract class CustomPropertyEffect extends PropertyEffect{
    public readonly Affects: string
    
    public abstract readonly Duration: number;
    public abstract readonly Strength: defined;
    public abstract readonly Priority?: number

    constructor (affects: string) {
        super()
        this.Affects = affects
    }
}