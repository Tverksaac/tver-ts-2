import { CharacterInfo, CharacterInstance } from "shared/tver/utility/interfaces";

export class Character {
    instance: CharacterInstance

    constructor(from_instance: CharacterInstance) {
        this.instance = from_instance
    }

    public GetCharacterInfo() {
        const info = {} as CharacterInfo
        
        info.instance = this.instance

        return info
    }
}