/** Property names for a given Instance type. */
export type PropertyNames<OfInstance extends Instance> = keyof WritableInstanceProperties<OfInstance>
/** Writable property names (alias) used for effect targeting. */
export type Affects<T extends Instance> = keyof WritableInstanceProperties<T>
/** Strength type for a property effect, derived from the property type. */
export type Strength<ConnectedInstance extends Instance, Name extends Affects<ConnectedInstance>> = ConnectedInstance[Name]
/** Effect type for a stat effect. */
export type EffectType = "Raw" | "Modifier"
/** Lifecycle states for effects. */
export type EffectState = "Ready" | "On" | "Off" | "Ended"
/** Lifecycle states for timers. */
export type TimerState = "Ready" | "Running" | "Paused"

export type StatusEffectGenericParams = {
    OnApply: defined[],
    OnStart: defined[],
    OnResume: defined[],
    OnPause: defined[],
    OnEnd: defined[],
    OnRemove: defined[]
}

/** Default values for StatusEffectGenericParams */
type DefaultStatusEffectGenericParams = {
    OnApply: [],
    OnStart: [],
    OnResume: [],
    OnPause: [],
    OnEnd: [],
    OnRemove: []
}

/** Merge partial params with defaults, allowing only specified params to be provided */
export type MergedStatusEffectParams<Params extends Partial<StatusEffectGenericParams>> = {
    [K in keyof StatusEffectGenericParams]: [Params[K]] extends [undefined]
        ? DefaultStatusEffectGenericParams[K]
        : [Params[K]] extends [never]
        ? DefaultStatusEffectGenericParams[K]
        : Params[K] extends defined[] 
        ? Params[K]
        : DefaultStatusEffectGenericParams[K]
}