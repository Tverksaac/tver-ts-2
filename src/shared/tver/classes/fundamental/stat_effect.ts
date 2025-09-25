type AffectType<ConnectedInstance extends Instance> = ExtractKeys<WritableInstanceProperties<ConnectedInstance>, number>
type EffectType = "Raw" | "Modifer"

export abstract class StrictStatEffect<ConnectedInstance extends Instance> {
    public readonly affects: AffectType<ConnectedInstance>

    public abstract readonly duration: number
    public abstract readonly strength: number
    public abstract readonly effect_type: EffectType

    constructor (_affects: AffectType<ConnectedInstance>) {
        this.affects = _affects
    }
}

export abstract class CustomStatEffect {
    public readonly affects: string

    public abstract readonly duration: number
    public abstract readonly strength: number
    public abstract readonly effect_type: EffectType

    constructor (_affects: string) {
        this.affects = _affects
    }
}