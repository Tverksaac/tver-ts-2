export interface CharacterInstance extends Instance {
    Humanoid: Humanoid
}

export interface CompoundEffectInfo {
    id: number,
    carrier_id: number,
    
}
export interface SkillInfo {}
export interface CharacterInfo {
    instance: Instance,
    id: number

    skills: Map<number, SkillInfo>
    compound_effects: Map<number, CompoundEffectInfo>
}