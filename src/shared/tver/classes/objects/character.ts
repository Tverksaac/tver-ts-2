import Signal from "@rbxts/signal";
import { config } from "shared/tver";
import { CharacterInfo, CharacterInstance } from "shared/tver/utility/_ts_only/interfaces";
import { get_id, map_to_array } from "shared/tver/utility/utils";
import { ConnectedStat, SeparatedStat } from "../fundamental/stat";
import { ConnectedProperty, SeparatedProperty } from "../fundamental/property";
import { AppliedCompoundEffect, CompoundEffect } from "./compound_effect";
import { CustomStatEffect, StrictStatEffect } from "../fundamental/stat_effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../fundamental/property_effect";
import { Affects } from "shared/tver/utility/_ts_only/types";
import { effect } from "@rbxts/charm";

export class Character {
    private static readonly CharactersMap = new Map<CharacterInstance, Character>()

    public static readonly CharacterAdded = new Signal<(Character: Character) => void>
    public static readonly CharacterRemoved = new Signal<(Character: Character) => void>

    public readonly instance: CharacterInstance
    public readonly humanoid: Humanoid
    public readonly id: number

    private readonly _stats = [] as ConnectedStat<Humanoid, ExtractKeys<WritableInstanceProperties<Humanoid>, number>>[]
    private readonly _properties = [] as ConnectedProperty<Humanoid, WritablePropertyNames<InstanceProperties<Humanoid>>>[]
    private readonly _custom_stats = [] as (SeparatedStat | ConnectedStat<never, never>)[]
    private readonly _custom_properties = [] as (SeparatedProperty<defined> | ConnectedProperty<never, never>)[]

    private readonly _effects = [] as AppliedCompoundEffect[]
    private readonly _property_effects = [] as (StrictPropertyEffect<Humanoid, Affects<Humanoid>> | CustomPropertyEffect)[]
    private readonly _stat_effects = [] as (StrictStatEffect<Humanoid> | CustomStatEffect)[]

    public readonly EffectApplied = new Signal()
    public readonly EffectRemoved = new Signal()

    static GetCharacterFromId(id: number): Character | undefined {
        this.CharactersMap.forEach((character) => {
            if (character.id === id) {
                return character
            }
        })
        return undefined
    }
    static GetCharacterFromInstance(instance: CharacterInstance): Character | undefined {
        this.CharactersMap.forEach((character, key) => {
            if (key === instance) {
                return character
            }
        })
        return undefined
    }

    static GetAllCharactersMap(): Map<CharacterInstance, Character> {
        return this.CharactersMap
    }

    static GetAllCharactersArray(): Character[] {
        return map_to_array(this.GetAllCharactersMap())
    }

    constructor(from_instance: CharacterInstance) {
        if (!config.CharacterCanBeCreatedOnClient) {
            error("Character can't be created on client!")
        }

        this.id = get_id()
        this.instance = from_instance
        this.humanoid = this.instance.Humanoid

        //Setup Basic Stats & Properties
        this._stats = [
            new ConnectedStat<Humanoid, "Health">("Health", 100, this.humanoid, "Health"),
            new ConnectedStat<Humanoid, "WalkSpeed">("WalkSpeed", 16, this.humanoid, "WalkSpeed"),
            new ConnectedStat<Humanoid, "JumpHeight">("JumpHeight", 7.2, this.humanoid, "JumpHeight")
        ]
        this._properties = [
            new ConnectedProperty<Humanoid, "AutoRotate">("AutoRotate", true, this.humanoid, "AutoRotate", true)
        ]

        Character.CharactersMap.set(this.instance, this)
        Character.CharacterAdded.Fire(this) 
    }
    public Destroy() {
        Character.CharacterRemoved.Fire(this)

        Character.CharactersMap.delete(this.instance)
    }

    public ApplyEffect(effect_to_apply: CompoundEffect) {
        const applied_effect = effect_to_apply.ApplyTo(this)

        this._effects.push(applied_effect)
    }

    public GetAppliedEffectsMap(): Map<string, AppliedCompoundEffect> {
       const map = new Map<string, AppliedCompoundEffect>

       this._effects.forEach((effect) => {
        map.set(effect.name, effect)
       })

       return map
    }

    public GetAppliedEffectsArray(): Array<AppliedCompoundEffect> {
        return map_to_array(this.GetAppliedEffectsMap())
    }

    public GetCharacterInfo() {
        const info = {} as CharacterInfo
        
        info.instance = this.instance
        info.id = this.id

        return info
    }
}