import { Effect } from "./effect"

type AffectType<ConnectedInstance extends Instance> = ExtractKeys<WritableInstanceProperties<ConnectedInstance>, number>
type EffectType = "Raw" | "Modifer"

abstract class StatEffect extends Effect {

}

export abstract class StrictStatEffect<ConnectedInstance extends Instance> extends StatEffect{
    public readonly Affects: AffectType<ConnectedInstance>

    public abstract readonly Strength: number
    public abstract readonly EffectType: EffectType

    constructor (_affects: AffectType<ConnectedInstance>) {
        super()
        this.Affects = _affects
    }
}

export abstract class CustomStatEffect extends StatEffect {
    public readonly Affects: string

    public abstract readonly Strength: number
    public abstract readonly EffectType: EffectType

    constructor (_affects: string) {
        super()
        this.Affects = _affects
    }
}