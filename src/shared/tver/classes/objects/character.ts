import Signal from "@rbxts/signal";
import { CharacterInfo, CompoundEffectInfo, SkillInfo } from "shared/tver/utility/_ts_only/interfaces";
import { dwlog, elog, get_handler, get_id, get_logger, is_client_context, is_server_context, map_to_array } from "shared/tver/utility/utils";
import { ConnectedStat, SeparatedStat } from "../fundamental/stat";
import { ConnectedProperty, SeparatedProperty } from "../fundamental/property";
import { AppliedCompoundEffect } from "./compound_effect";
import { CustomStatEffect, StrictStatEffect } from "../core/stat_effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../core/property_effect";
import { Affects } from "shared/tver/utility/_ts_only/types";
import { Server } from "../main/server";
import { Client } from "../main/client";
import { ClientEvents, ServerEvents } from "shared/tver/network/networking";
import { Players } from "@rbxts/services";
import { observe } from "@rbxts/charm";
import { client_atom } from "shared/tver/utility/shared";

const LOG_KEY = "[CHARACTER]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

type _possible_stats_type = (ConnectedStat<Humanoid, ExtractKeys<WritableInstanceProperties<Humanoid>, number>>)
type _possible_custom_stats_type = (SeparatedStat | ConnectedStat<never, never>)
type _possible_properties_type = (ConnectedProperty<Humanoid, WritablePropertyNames<InstanceProperties<Humanoid>>>)
type _possible_custom_properties_type = (SeparatedProperty<defined> | ConnectedProperty<never, never>)
type _every_possible_stats_type = _possible_stats_type | _possible_custom_stats_type
type _every_possible_properties_type = _possible_properties_type | _possible_custom_properties_type

export class Character {
    public static readonly CharactersMap = new Map<Instance, Character>()

    public static readonly CharacterAdded = new Signal<(Character: Character) => void>
    public static readonly CharacterRemoved = new Signal<(Character: Character) => void>

    public readonly player?: Player | undefined
    public readonly instance: Instance
    public readonly humanoid: Humanoid
    public readonly id: number

    private replication_done: boolean
    = is_client_context()

    private readonly _stats = new Map<string, _possible_stats_type>()
    private readonly _properties = new Map<string, _possible_properties_type>()
    private readonly _custom_stats = new Map<string, _possible_custom_stats_type>()
    private readonly _custom_properties = new Map<string, _possible_custom_properties_type>()

    private readonly _effects = [] as AppliedCompoundEffect[]
    private readonly _property_effects = [] as (StrictPropertyEffect<Humanoid, Affects<Humanoid>> | CustomPropertyEffect)[]
    private readonly _stat_effects = [] as (StrictStatEffect<Humanoid> | CustomStatEffect)[]

    private readonly _effect_changed = new Signal()

    public readonly EffectApplied = new Signal<(AppliedEffect: AppliedCompoundEffect) => void>()
    public readonly EffectRemoved = new Signal<(RemovedEffect: AppliedCompoundEffect) => void>()
    public readonly SkillAdded = new Signal<(AddedSkill: unknown) => void>()
    public readonly SkillRemoved = new Signal<(RemovedSkill: unknown) => void>()

    static GetCharacterFromId(id: number): Character | undefined {
        let to_return
        this.GetAllCharactersArray().forEach((character) => {
            if (character.id === id) {
                to_return = character
            }
        })
        return to_return
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

    //Yields!
    constructor(from_instance: Instance) {
        this.id = is_server_context()? get_id() : 1
        this.instance = from_instance
        this.humanoid = this.instance.FindFirstChildWhichIsA("Humanoid") || elog(this.instance + " Do not have Humanoid as Child!")
        this.player = Players.GetPlayerFromCharacter(this.instance)

        //Setup Basic Stats & Properties
        //IMPORTANT: Name of property/stat should be same as what it affects
        const _stats = [
            new ConnectedStat<Humanoid, "MaxHealth">("MaxHealth", 100, this.humanoid),
            new ConnectedStat<Humanoid, "Health">("Health", 100, this.humanoid),
            new ConnectedStat<Humanoid, "WalkSpeed">("WalkSpeed", 25, this.humanoid),
            new ConnectedStat<Humanoid, "JumpHeight">("JumpHeight", 7.2, this.humanoid)
        ]
        const _properties = [
            new ConnectedProperty<Humanoid, "AutoRotate">("AutoRotate", true, this.humanoid)
        ]

        _stats.forEach((stat) => {
            this.AddStat(stat)
        })
        _properties.forEach((prop) => {
            this.AddProperty(prop)
        })

        //init
        this.init() // should be here, then everything else, so character fully loads
        //init

        Character.CharactersMap.set(this.instance, this)
        Character.CharacterAdded.Fire(this)
    }

    //PUBLIC: MAIN
    public GetCharacterInfo() {
        const info = {} as CharacterInfo

        const compound_effects = new Map<string, CompoundEffectInfo>()
        const skills = new Map<string, SkillInfo>()
        this._effects.forEach((effect) => {
            compound_effects.set(effect.Name, {
                id: effect.id,
                carrier_id: effect.CarrierID
            })
        })
        
        info.instance = this.instance
        info.compound_effects = compound_effects
        info.id = this.id
        
        return info
    }

    //PUBLIC: STATUS EFFECTS
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
    public GetAppliedEffectFromName(name: string): AppliedCompoundEffect | undefined {
        let to_return
        this._effects.forEach((effect) => {
            if (effect.Name === name) {
                to_return = effect
            }
        })
        return to_return
    }
    public GetAppliedEffectFromId(id: number): AppliedCompoundEffect | undefined {
        let to_return
        this._effects.forEach((effect) => {
            if (effect.id === id) {
                to_return = effect
            }
        })
        return to_return
    }

    public AddStat(stat: _every_possible_stats_type): boolean {
        if (this._stats.get(stat.name) || this._custom_stats.get(stat.name)) {
            log.w(stat.name + " Stat" + " is already exists in " + this.instance.Name + "!")
            return false
        }
        if (stat.getType() === "ConnectedStat") {
            this._stats.set(stat.name, stat as _possible_stats_type)
        } else {
            this._custom_stats.set(stat.name, stat as _possible_custom_stats_type)
        }
        return true
    }
    public AddProperty(prop: _every_possible_properties_type): boolean {
        if (this._properties.get(prop.name) || this._custom_properties.get(prop.name)) {
            log.w(prop.name + " is already exists in " + this.instance.Name + "!")
            return false
        }
        if (prop.getType() === "ConnectedProperty") {
            this._properties.set(prop.name, prop as _possible_properties_type)
        } else {
            this._custom_properties.set(prop.name, prop as _possible_custom_properties_type)
        }
        return true
    }

    //PUBLIC: DESTROY
    public Destroy() {
        Character.CharacterRemoved.Fire(this)
        Character.CharactersMap.delete(this.instance)
    }
    
    // @internal //
    //STATUS EFFECTS

    //!!Dont use, even tho its public!!---
    public _internal_apply_effect(applied_effect: AppliedCompoundEffect) {
        this._effects.push(applied_effect)
        this.EffectApplied.Fire(applied_effect)
    }
    public _internal_remove_effect(find_from: string | number): AppliedCompoundEffect | undefined {
        const effect = type(find_from) === "string"? this.GetAppliedEffectFromName(find_from as string) : this.GetAppliedEffectFromId(find_from as number)

        this._effects.forEach((val, index) => {
            if (val === effect) {
                this.EffectRemoved.Fire(effect)
                this._effects.remove(index)
            }
        })
        return effect
    }
    //^^^!!Dont use, even tho its public!!---^^^

    private _start_listen_to_effect_changes() {
        const listen_to: Signal[] = [
            this.EffectApplied,
            this.EffectRemoved,
            this._effect_changed
        ]
        listen_to.forEach(signal => signal.Connect(() => {
            this._handle_effects()
        }))
    }

    private _update_effects_maps() {
        const effects = this.GetAppliedEffectsMap()

        this._stat_effects.clear()
        this._property_effects.clear()

        effects.forEach((effect, key) => {
            if (effect.state.GetState() === "Ended") return

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

            if (!member) {
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
                 log.e(effect + " have wrong effect type property! /n Should be 'Raw' or 'Modifer' but have value of: " + effect.EffectType)
            }

            calculated.set(member.Affects, member)
        })

        return calculated
    }

    private _update_stats() {
        const calculated = this._calculate_stat_effects()

        //return stats to base values
        const _return_to_base_value = (stat: _every_possible_stats_type) => {
            if (calculated.has(stat.name)) return
            stat.Bonus.Modifer.Set(1)
            stat.Bonus.Raw.Set(0)

        }
        this._stats.forEach(_return_to_base_value)
        this._custom_stats.forEach(_return_to_base_value)

        calculated.forEach((stat, key) => {
            let stat_to_affect
            stat_to_affect = this._stats.get(stat.Affects) || this._custom_stats.get(stat.Affects)
            if (stat_to_affect) {
                //stat to affect is innate stat
                stat_to_affect.Bonus.Modifer.Set(stat.Modifer)
                 stat_to_affect.Bonus.Raw.Set(stat.Raw)               
            } else {
                log.e(stat + " Cant affect any of stats becuase theres no stat with name: " + stat.Affects)
            } 
        })
    }
    private _update_properties() {
        const calculated = this._calculate_property_effects()

        const _return_to_base_value = (property: _every_possible_properties_type) => {
            if (calculated.has(property.name)) return
            property.Reset()
        }

        this._properties.forEach(_return_to_base_value)
        this._custom_properties.forEach(_return_to_base_value)

        calculated.forEach((prop, key) => {
            let prop_to_affect
            prop_to_affect = this._properties.get(prop.Affects)

            if (prop_to_affect) {
                //property to affect is innate property
                if (typeOf(prop.Strength) === typeOf(prop_to_affect.Get())) {
                    prop_to_affect.Set(prop.Strength as never)
                } else {
                    log.e(prop + " Have wrong Strength value! /n Cant assign " + typeOf(prop.Strength) + "to " + typeOf(prop_to_affect.Get()))
                }
                
            } else {
                prop_to_affect = this._custom_properties.get(prop.Affects)

                if (prop_to_affect) {
                    //property to affect is custom added property
                    if (typeOf(prop.Strength) === typeOf(prop_to_affect.Get())) {
                        prop_to_affect.Set(prop.Strength as never)
                    } else {
                        log.e(prop + " Have wrong Strength value! /n Cant assign " + typeOf(prop.Strength) + "to " + typeOf(prop_to_affect.Get()))
                    }
                } else {
                    log.e(prop + " Cant affect any of properties becuase theres no property with name: " + prop.Affects)
                }
            }
        })
    }

    //REPLICATION
    private _update_server_atom() {
        const server = get_handler() as Server
        server.atom((state) => {
            const new_state = table.clone(state)
            new_state.set(this.instance, this.GetCharacterInfo())

            dlog.l("Server atom was updated!")
            print(new_state)

            return new_state
        })
    }

    private _connect_server_atom_updating() {
        const signals = [
            this.EffectApplied,
            this.EffectRemoved,
            this.SkillAdded,
            this.SkillRemoved
        ]

        signals.forEach((signal) => {
            signal.Connect(() => {
                this._update_server_atom()
            })
        })
    }

    private _replicate_compound_effect(from: string) {
        print("Replicating: " + from)
    }

    private _server_replication() {
        const server = get_handler() as Server
        if (!server) log.e("Server not found! Maybe you forgot to Create it?")
        
        this._connect_server_atom_updating()
        this._update_server_atom()

        if (this.player) {
            ServerEvents.character_replication_done.connect((player) => {
                this.replication_done = true
            })
        } else {
            this.replication_done = true
        }

        dlog.l("Server-Side Character was succesfully created for " + this.instance.Name)
    }
    private _client_replication() {
        if (!this.player) return
        const client = get_handler() as Client
        if (!client) {log.e("Client not found! Maybe you forgot to Create it?")}

        observe(
            () => client_atom()?.compound_effects || new Map<string, CompoundEffectInfo>(),
            (_, key) => this._replicate_compound_effect(key)
        )

        dlog.l("Client-Side Character was succesfully created for " + this.instance.Name)
        
        ClientEvents.character_replication_done.fire()
    }
    private _start_replication() {
        is_client_context()? this._client_replication() : this._server_replication()
    }

    //MAIN
    private _handle_effects() {
        this._update_effects_maps()
        this._update_stats()
        this._update_properties()
    }

    private init() {
        this._start_replication()
        while(!this.replication_done && !is_client_context()) {task.wait()} // yield until replciation is done
        this._start_listen_to_effect_changes()
        return true
    }
}