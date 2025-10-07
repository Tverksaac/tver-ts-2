import Signal from "@rbxts/signal";
import { config } from "shared/tver";
import { CharacterInfo } from "shared/tver/utility/_ts_only/interfaces";
import { get_handler, get_id, is_client_context, is_server_context, map_to_array, setup_humanoid } from "shared/tver/utility/utils";
import { ConnectedStat, SeparatedStat } from "../fundamental/stat";
import { ConnectedProperty, SeparatedProperty } from "../fundamental/property";
import { AppliedCompoundEffect, CompoundEffect } from "./compound_effect";
import { CustomStatEffect, StrictStatEffect } from "../core/stat_effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../core/property_effect";
import { Affects } from "shared/tver/utility/_ts_only/types";
import { Server } from "../main/server";
import { Client } from "../main/client";

export class Character {
    private static readonly CharactersMap = new Map<Instance, Character>()

    public static readonly CharacterAdded = new Signal<(Character: Character) => void>
    public static readonly CharacterRemoved = new Signal<(Character: Character) => void>

    public readonly instance: Instance
    public readonly humanoid: Humanoid
    public readonly id: number

    private readonly _stats = new Map<string, (ConnectedStat<Humanoid, ExtractKeys<WritableInstanceProperties<Humanoid>, number>>)>()
    private readonly _properties = new Map<string, (ConnectedProperty<Humanoid, WritablePropertyNames<InstanceProperties<Humanoid>>>)>()
    private readonly _custom_stats = new Map<string, (SeparatedStat | ConnectedStat<never, never>)>()
    private readonly _custom_properties = new Map<string, (SeparatedProperty<defined> | ConnectedProperty<never, never>)>()

    private readonly _effects = [] as AppliedCompoundEffect[]
    private readonly _property_effects = [] as (StrictPropertyEffect<Humanoid, Affects<Humanoid>> | CustomPropertyEffect)[]
    private readonly _stat_effects = [] as (StrictStatEffect<Humanoid> | CustomStatEffect)[]

    private readonly _effect_changed = new Signal()

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
    static GetCharacterFromInstance(instance: Instance): Character | undefined {
        this.CharactersMap.forEach((character, key) => {
            if (key === instance) {
                return character
            }
        })
        return undefined
    }

    static GetAllCharactersMap(): Map<Instance, Character> {
        return this.CharactersMap
    }

    static GetAllCharactersArray(): Character[] {
        return map_to_array(this.GetAllCharactersMap())
    }

    constructor(from_instance: Instance) {
        if (is_client_context() && !config.CharacterCanBeCreatedOnClient) {
            warn("Character can't be created on client!")
        }

        this.id = get_id()
        this.instance = from_instance
        this.humanoid = this.instance.FindFirstChildWhichIsA("Humanoid") || setup_humanoid(this.instance)

        //Setup Basic Stats & Properties
        //IMPORTANT: Name of property/stat should be same as what it affects
        const _stats = [
            new ConnectedStat<Humanoid, "Health">("Health", 100, this.humanoid, "Health"),
            new ConnectedStat<Humanoid, "WalkSpeed">("WalkSpeed", 16, this.humanoid, "WalkSpeed"),
            new ConnectedStat<Humanoid, "JumpHeight">("JumpHeight", 7.2, this.humanoid, "JumpHeight")
        ]
        const _properties = [
            new ConnectedProperty<Humanoid, "AutoRotate">("AutoRotate", true, this.humanoid, "AutoRotate", true)
        ]

        _stats.forEach((stat) => {
            this._stats.set(stat.name, stat)
        })
        _properties.forEach((prop) => {
            this._properties.set(prop.name, prop)
        })

        //init
        Character.CharactersMap.set(this.instance, this)
        Character.CharacterAdded.Fire(this)

        this.start_replication()
    }

    //PUBLIC
    public ApplyEffect(effect_to_apply: CompoundEffect) {
        const applied_effect = effect_to_apply.ApplyTo(this)

        this._effects.push(applied_effect)
    }

    public GetAppliedEffectsMap(): Map<string, AppliedCompoundEffect> {
       const map = new Map<string, AppliedCompoundEffect>()

       this._effects.forEach((effect) => {
        map.set(effect.Name, effect)
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

    public Destroy() {
        Character.CharacterRemoved.Fire(this)
        Character.CharactersMap.delete(this.instance)
    }
    
    // @internal //
    //STATUS EFFECTS
    private _update_effects_maps() {
        const effects = this.GetAppliedEffectsMap()

        effects.forEach((effect, key) => {
            if (effect.state.GetState() === "Ended") return

            this._stat_effects.clear()
            this._property_effects.clear()

            effect.StatEffects.forEach((stat_effect) => {
                this._stat_effects.push(stat_effect)
            })
            effect.PropertyEffects.forEach((property_effect) => {
                this._property_effects.push(property_effect)
            })
        })
    }

    private _calculate_property_effects() {
        const calculated = new Map<string, {Affects: string, Strength: unknown, Priority: number}>()

        this._property_effects.forEach((effect) => {
            if (effect.state.GetState() !== "On") {
                return
            }
            
            let member = calculated.get(effect.Affects)

            if (member) {} else {
                member = {
                    Affects: effect.Affects,
                    Strength: effect.Strength,
                    Priority: effect.Priority || 1
                }
            }

            if (effect.Priority || 1 > member.Priority) {
                member.Priority = effect.Priority || 1
                member.Strength = effect.Strength
            }

            calculated.set(member.Affects, member)
        })

        return calculated as Map<string, {Affects: string, Strength: unknown, Priority: number}>
    }
    private _calculate_stat_effects() {
        const calculated = new Map<string, {Affects: string, Raw: number, Modifer: number}>()

        this._stat_effects.forEach((effect) => {
            if (effect.state.GetState() !== "On") {
                return
            }

            let member = calculated.get(effect.Affects)
            const effect_type = effect.EffectType

            if (member) {} else {
                member = {
                    Affects: effect.Affects,
                    Raw: 0,
                    Modifer: 1
                }
            }

            if (effect_type === "Modifer") {
                member.Modifer = member.Modifer * effect.Strength
            } else if (effect_type === "Raw") {
                member.Raw = member.Raw + effect.Strength
             } else {
                 error(effect + " have wrong effect type property! /n Should be 'Raw' or 'Modifer' but have value of: " + effect.EffectType)
            }

            calculated.set(member.Affects, member)
        })

        return calculated
    }

    private _update_stats() {
        const calculated = this._calculate_stat_effects()

        calculated.forEach((stat, key) => {
            let stat_to_affect
            stat_to_affect = this._stats.get(stat.Affects)

            if (stat_to_affect) {
                //stat to affect is innate stat
                stat_to_affect.Bonus.Modifer.Set(stat.Modifer)
                stat_to_affect.Bonus.Raw.Set(stat.Raw)               
            } else {
                stat_to_affect = this._custom_stats.get(stat.Affects)

                if (stat_to_affect) {
                    //stat to affect is custom stat
                    stat_to_affect.Bonus.Modifer.Set(stat.Modifer)
                    stat_to_affect.Bonus.Raw.Set(stat.Raw)  
                } else {
                    error(stat + " Cant affect any of stats becuase theres no stat with name: " + stat.Affects)
                } 
            }
        })
    }
    private _update_properties() {
        const calculated = this._calculate_property_effects()

        calculated.forEach((prop, key) => {
            let prop_to_affect
            prop_to_affect = this._properties.get(prop.Affects)

            if (prop_to_affect) {
                //property to affect is innate property
                if (typeOf(prop.Strength) === typeOf(prop_to_affect.Get())) {
                    prop_to_affect.Set(prop.Strength as never)
                } else {
                    error(prop + " Have wrong Strength value! /n Cant assign " + typeOf(prop.Strength) + "to " + typeOf(prop_to_affect.Get()))
                }
                
            } else {
                prop_to_affect = this._custom_properties.get(prop.Affects)

                if (prop_to_affect) {
                    //property to affect is custom added property
                    if (typeOf(prop.Strength) === typeOf(prop_to_affect.Get())) {
                        prop_to_affect.Set(prop.Strength as never)
                    } else {
                        error(prop + " Have wrong Strength value! /n Cant assign " + typeOf(prop.Strength) + "to " + typeOf(prop_to_affect.Get()))
                    }
                } else {
                    error(prop + " Cant affect any of properties becuase theres no property with name: " + prop.Affects)
                }
            }
        })
    }

    //REPLICATION
    private start_replication() {
        print(is_client_context() + ": IS CLIENT CONTEXT")
        if (is_client_context()) {
            const client = get_handler() as Client
            if (!client) error("Client not found! Maybe you forgot to Create it?")

        } else if (is_server_context()) {
            const server = get_handler() as Server
            print(server)
            if (!server) error("Server not found! Maybe you forgot to Create it?")
            
            server.atom((state) => {
                const new_state = table.clone(state)

                const data = new_state.get(this.instance)
                if (!data) {
                    new_state.set(this.instance, this.GetCharacterInfo())
                }

                return new_state
            })

            print("NEW SERVER ATOM STATE: " + server.atom())
        }        
    }

    //MAIN
    private _handle_effects() {
        this._update_effects_maps()
        this._update_stats()
        this._update_properties()
    }
}