import { Effect } from "./effect"

type AffectType<ConnectedInstance extends Instance> = ExtractKeys<WritableInstanceProperties<ConnectedInstance>, number>
type EffectType = "Raw" | "Modifer"

abstract class StatEffect extends Effect {

}

export abstract class StrictStatEffect<ConnectedInstance extends Instance> extends StatEffect{
    public readonly affects: AffectType<ConnectedInstance>

    public abstract readonly duration: number
    public abstract readonly strength: number
    public abstract readonly effect_type: EffectType

    constructor (_affects: AffectType<ConnectedInstance>) {
        super()
        this.affects = _affects
    }
}

export abstract class CustomStatEffect extends StatEffect {
    public readonly affects: string

    public abstract readonly duration: number
    public abstract readonly strength: number
    public abstract readonly effect_type: EffectType

    constructor (_affects: string) {
        super()
        this.affects = _affects
    }
}