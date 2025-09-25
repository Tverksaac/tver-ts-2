import { Affects, Strength } from "shared/tver/utility/_ts_only/types"

export abstract class StrictPropertyEffect<ConnectedInstance extends Instance, Name extends Affects<ConnectedInstance>> {
    public readonly affects: Affects<ConnectedInstance>

    public abstract readonly duration: number
    public abstract readonly strength: Strength<ConnectedInstance, Name>
    public readonly priority?: number

    constructor (affects: Affects<ConnectedInstance>) {
        this.affects = affects
    }
}

export abstract class CustomPropertyEffect {
    public readonly affects: string

    public abstract readonly duration: number
    public abstract readonly strength: defined
    public readonly priority?: number

    constructor (affects: string) {
        this.affects = affects
    }
}