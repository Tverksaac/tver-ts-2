import Signal from "@rbxts/signal";
import { config } from "shared/tver";
import { CharacterInfo, CharacterInstance } from "shared/tver/utility/interfaces";

let _character_id = 0;
function _get_id() {
    _character_id++
    return _character_id
}

export class Character {
    private static readonly CharactersMap = new Map<Instance, CharacterInfo>()

    public static readonly CharacterAdded = new Signal<(Character: Character) => void>
    public static readonly CharacterRemoved = new Signal<(Character: Character) => void>

    public readonly instance: CharacterInstance
    public readonly id: number

    constructor(from_instance: CharacterInstance) {
        if (!config.CharacterCanBeCreatedOnClient) {
            error("Character can't be created on client!")
        }

        this.id = _get_id()
        this.instance = from_instance

        Character.CharactersMap.set(this.instance, this)
        Character.CharacterAdded.Fire(this) 
    }

    public GetCharacterInfo() {
        const info = {} as CharacterInfo
        
        info.instance = this.instance
        info.id = this.id

        return info
    }
}