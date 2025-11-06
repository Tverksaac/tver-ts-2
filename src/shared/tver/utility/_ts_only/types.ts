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
    ConstructorParams: unknown[]
    OnStart: unknown[],
    OnResume: unknown[],
    OnPause: unknown[],
}
export type SkillGenericParams = {
    OnStart: unknown[],
    OnAbort: unknown[],
}
export type GetParamType<T, K extends (keyof StatusEffectGenericParams | keyof SkillGenericParams)> = 
    T extends { [P in K]: infer U } 
        ? U extends unknown[]
            ? U 
            : []
        : []
