import { Effect } from "./effect"

/** Instance property names of numeric stats for a connected instance. */
type AffectType<ConnectedInstance extends Instance> = ExtractKeys<WritableInstanceProperties<ConnectedInstance>, number>
/** How a stat effect applies: add raw value or multiply as modifier. */
type EffectType = "Raw" | "Modifer"

/** Base for effects that influence numeric stats. */
abstract class StatEffect extends Effect {
}

/**
 * Stat effect targeting a concrete instance stat.
 */
export abstract class StrictStatEffect<ConnectedInstance extends Instance> extends StatEffect{
    public readonly Affects: AffectType<ConnectedInstance>

    public abstract readonly Strength: number
    public abstract readonly EffectType: EffectType

    constructor (_affects: AffectType<ConnectedInstance>) {
        super()
        this.Affects = _affects
    }
}

/**
 * Stat effect targeting a custom stat identified by string key.
 */
export abstract class CustomStatEffect extends StatEffect {
    public readonly Affects: string

    public abstract readonly Strength: number
    public abstract readonly EffectType: EffectType

    constructor (_affects: string) {
        super()
        this.Affects = _affects
    }
}