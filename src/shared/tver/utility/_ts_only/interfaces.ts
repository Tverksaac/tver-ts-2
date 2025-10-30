/** Roblox character instance with a `Humanoid` child. */
export interface CharacterInstance extends Instance {
    Humanoid: Humanoid
}

/** Minimal info needed to represent an applied compound effect. */
export interface CompoundEffectInfo {
    id: number,
    carrier_id: number,
    
}
export interface SkillInfo {}
/** Minimal info needed to represent a character. */
export interface CharacterInfo {
    instance: Instance,
    id: number

    skills: Map<string, SkillInfo>
    compound_effects: Map<string, CompoundEffectInfo>
}