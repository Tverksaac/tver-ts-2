export interface CharacterInstance extends Instance {
    Humanoid: Humanoid
}

export interface CompoundEffectInfo {}
export interface SkillInfo {}

export interface CharacterInfo {
    instance: CharacterInstance,
    id: number

    skills: Map<string, SkillInfo>
    effects_applied: Map<string, CompoundEffectInfo>
}