import { SoundService } from "@rbxts/services"
import { Timer } from "@rbxts/timer"
import { Affects, Strength } from "shared/tver/utility/_ts_only/types"
import { Effect } from "./effect"

abstract class PropertyEffect extends Effect {
    public abstract priority?: number

    public SetPriority(new_priority: number) {
        this.priority = new_priority
    }
}

export abstract class StrictPropertyEffect<ConnectedInstance extends Instance, Name extends Affects<ConnectedInstance>> extends PropertyEffect {
    public readonly affects: Affects<ConnectedInstance>

    public abstract readonly duration: number
    public abstract readonly strength: Strength<ConnectedInstance, Name>
    public readonly priority?: number

    constructor (affects: Affects<ConnectedInstance>) {
        super()
        this.affects = affects
    }
}

export abstract class CustomPropertyEffect extends PropertyEffect{
    public readonly affects: string
    public readonly priority?: number

    constructor (affects: string) {
        super()
        this.affects = affects
    }
}