import { Effect } from "./effect"
import { EffectType } from "shared/tver/utility/_ts_only/types"

/** Instance property names of numeric stats for a connected instance. */
type AffectType<ConnectedInstance extends Instance> = ExtractKeys<WritableInstanceProperties<ConnectedInstance>, number>
// EffectType is imported from shared types

/** Base for effects that influence numeric stats. */
abstract class StatEffect extends Effect {}

/**
 * Stat effect targeting a concrete instance stat.
 */
export abstract class StrictStatEffect<ConnectedInstance extends Instance> extends StatEffect{
    public readonly Affects!: AffectType<ConnectedInstance>

    public abstract readonly Strength: number
    public abstract readonly EffectType: EffectType
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