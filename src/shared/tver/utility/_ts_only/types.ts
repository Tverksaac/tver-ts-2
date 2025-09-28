export type PropertyNames<OfInstance extends Instance> = keyof WritableInstanceProperties<OfInstance>
export type Affects<T extends Instance> = keyof WritableInstanceProperties<T>
export type Strength<ConnectedInstance extends Instance, Name extends Affects<ConnectedInstance>> = ConnectedInstance[Name]
export type EffectState = "Ready" | "On" | "Off" | "Ended"