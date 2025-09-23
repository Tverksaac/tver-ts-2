import { CharacterInfo, CharacterInstance } from "shared/tver/utility/interfaces";

let _character_id = 0;
function _get_id() {
    _character_id++
    return _character_id
}

export class Character {
    private static readonly CharactersMap = new Map<Instance, CharacterInfo>()

    instance: CharacterInstance

    id = _get_id()

    constructor(from_instance: CharacterInstance) {
        this.instance = from_instance
    }

    public GetCharacterInfo() {
        const info = {} as CharacterInfo
        
        info.instance = this.instance
        info.id = this.id

        return info
    }
}