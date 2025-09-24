export interface CharacterInstance extends Instance {
    Humanoid: Humanoid
}

export interface CharacterInfo {
    instance: CharacterInstance,
    id: number
}