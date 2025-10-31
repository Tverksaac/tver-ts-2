//!native
import Signal from "@rbxts/signal";
import { CharacterInfo, CompoundEffectInfo, SkillInfo } from "shared/tver/utility/_ts_only/interfaces";
import { elog, get_handler, get_id, get_logger, is_client_context, is_server_context, map_to_array } from "shared/tver/utility/utils";
import { ConnectedStat, SeparatedStat } from "../fundamental/stat";
import { ConnectedProperty, SeparatedProperty } from "../fundamental/property";
import { AppliedCompoundEffect, CompoundEffect, GetCompoundEffectFromName } from "./compound_effect";
import { CustomStatEffect, StrictStatEffect } from "../core/stat_effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../core/property_effect";
import { Affects } from "shared/tver/utility/_ts_only/types";
import { Server } from "../main/server";
import { Client } from "../main/client";
import { ClientEvents, ServerEvents } from "shared/tver/network/networking";
import { Players } from "@rbxts/services";
import { observe } from "@rbxts/charm";
import { client_atom } from "shared/tver/utility/shared";
import { find } from "@rbxts/immut/src/table";
import { Janitor } from "@rbxts/janitor";

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
    /**
     * Global registry of all live `Character` instances keyed by their Roblox `Instance`.
     */
    public static readonly CharactersMap = new Map<Instance, Character>()
    /**
     * O(1) lookup map for characters by numeric id.
     */
    public static readonly CharactersById = new Map<number, Character>()

    /**
     * Fires when a `Character` is constructed and registered.
     */
    public static readonly CharacterAdded = new Signal<(Character: Character) => void>
    /**
     * Fires when a `Character` is destroyed and unregistered.
     */
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
    private readonly janitor = new Janitor()

    public readonly EffectApplied = new Signal<(AppliedEffect: AppliedCompoundEffect) => void>()
    public readonly EffectRemoved = new Signal<(RemovedEffect: AppliedCompoundEffect) => void>()
    public readonly SkillAdded = new Signal<(AddedSkill: unknown) => void>()
    public readonly SkillRemoved = new Signal<(RemovedSkill: unknown) => void>()
    /**
     * Fires once when replication is confirmed for this character.
     */
    public readonly ReplicationReady = new Signal()

    public readonly _manipulate: {
        _apply_effect: (effect: AppliedCompoundEffect) => void,
        _remove_effect: (find_from: string | number) => AppliedCompoundEffect | undefined,
    }

    /**
     * Look up a `Character` by its internal numeric id.
     */
    static GetCharacterFromId(id: number): Character | undefined {
        return this.CharactersById.get(id)
    }
    /**
     * Look up a `Character` by its Roblox `Instance`.
     */
    static GetCharacterFromInstance(instance: Instance): Character | undefined {
        return this.CharactersMap.get(instance)
    }

    /**
     * Get a map view of all characters keyed by instance.
     */
    static GetAllCharactersMap(): Map<Instance, Character> {
        return this.CharactersMap
    }

    /**
     * Get an array view of all characters.
     */
    static GetAllCharactersArray(): Character[] {
        return map_to_array(this.GetAllCharactersMap())
    }

    /**
     * Construct a `Character` from a Roblox `Instance` (expects a `Humanoid` child).
     * Yields on server until replication completes.
     */
    constructor(from_instance: Instance) {
        this.id = is_server_context()? get_id() : 1
        this.instance = from_instance
        this.humanoid = this.instance.FindFirstChildWhichIsA("Humanoid") || elog(this.instance + " Do not have Humanoid as Child!")
        this.player = Players.GetPlayerFromCharacter(this.instance)

        this._manipulate = {
            _apply_effect: (effect: AppliedCompoundEffect) => {
                this._compound_effect_only_apply_effect(effect)
            },
            _remove_effect: (find_from: string | number) => {
                return this._compound_effect_only_remove_effect(find_from)
            }
        }

        // Setup basic Stats & Properties
        // IMPORTANT: Name of property/stat should match the thing it affects
        const _stats = [
            new ConnectedStat<Humanoid, "MaxHealth">(this.humanoid, "MaxHealth", 100),
            new ConnectedStat<Humanoid, "Health">(this.humanoid, "Health", 100),
            new ConnectedStat<Humanoid, "WalkSpeed">(this.humanoid, "WalkSpeed", 16),
            new ConnectedStat<Humanoid, "JumpHeight">(this.humanoid, "JumpHeight", 7.2),
        ]
        const _properties = [
            new ConnectedProperty<Humanoid, "AutoRotate">(this.humanoid, "AutoRotate", true)
        ]

        _stats.forEach((stat) => {
            this.AddStat(stat)
        })
        _properties.forEach((prop) => {
            this.AddProperty(prop)
        })

        // init
        this.init() // should be here, then everything else, so character fully loads
        // init

        Character.CharactersMap.set(this.instance, this)
        Character.CharactersById.set(this.id, this)
        Character.CharacterAdded.Fire(this)
    }

    // PUBLIC: MAIN
    /**
     * Snapshot of this character for replication/state.
     */
    public GetCharacterInfo(): CharacterInfo {
        const info = {} as CharacterInfo

        const compound_effects = new Map<string, CompoundEffectInfo>()
        const skills = new Map<string, SkillInfo>()

        this._effects.forEach((effect) => {
            compound_effects.set(effect.Name, {
                id: effect.id,
                carrier_id: this.id
            })
        })
        
        info.instance = this.instance
        info.compound_effects = compound_effects
        info.skills = skills
        info.id = this.id
        
        return info
    }

    // PUBLIC: STATUS EFFECTS
    /**
     * Get a map of currently applied compound effects keyed by effect name.
     */
    public GetAppliedEffectsMap(): Map<string, AppliedCompoundEffect> {
       const map = new Map<string, AppliedCompoundEffect>()

       this._effects.forEach((effect) => {
        map.set(effect.Name, effect)
       })

       return map
    }
    /**
     * Get an array of currently applied compound effects.
     */
    public GetAppliedEffectsArray(): Array<AppliedCompoundEffect> {
        return [...this._effects]
    }
    /**
     * Find an applied effect by name.
     */
    public GetAppliedEffectFromName(name: string): AppliedCompoundEffect | undefined {
        for (const effect of this._effects) {
            if (effect.Name === name) return effect
        }
        return undefined
    }
    /**
     * Find an applied effect by id.
     */
    public GetAppliedEffectFromId(id: number): AppliedCompoundEffect | undefined {
        for (const effect of this._effects) {
            if (effect.id === id) return effect
        }
        return undefined
    }

    /**
     * Register a stat (connected or custom). Returns false if name already exists.
     */
    public AddStat(stat: _every_possible_stats_type): boolean {
        if (this._stats.get(stat.name) || this._custom_stats.get(stat.name)) {
            log.w(stat.name + " Stat" + " is already exists in " + this.instance.Name + "!")
            return false
        }
        if (tostring(getmetatable(stat)) === "ConnectedStat") {
            this._stats.set(stat.name, stat as _possible_stats_type)
        } else {
            this._custom_stats.set(stat.name, stat as _possible_custom_stats_type)
        }
        return true
    }
    /**
     * Register a property (connected or custom). Returns false if name already exists.
     */
    public AddProperty(prop: _every_possible_properties_type): boolean {
        if (this._properties.get(prop.name) || this._custom_properties.get(prop.name)) {
            log.w(prop.name + " is already exists in " + this.instance.Name + "!")
            return false
        }
        if (tostring(getmetatable(prop)) === "ConnectedProperty") {
            this._properties.set(prop.name, prop as _possible_properties_type)
        } else {
            this._custom_properties.set(prop.name, prop as _possible_custom_properties_type)
        }
        return true
    }

    /** Whether this character has a stat by name (connected or custom). */
    public HasStat(name: string): boolean {
        return this._stats.has(name) || this._custom_stats.has(name)
    }
    /** Whether this character has a property by name (connected or custom). */
    public HasProperty(name: string): boolean {
        return this._properties.has(name) || this._custom_properties.has(name)
    }
    /** Get a stat by name (connected or custom). */
    public GetStat(name: string): _every_possible_stats_type | undefined {
        return this._stats.get(name) || this._custom_stats.get(name)
    }
    /** Get a property by name (connected or custom). */
    public GetProperty(name: string): _every_possible_properties_type | undefined {
        return this._properties.get(name) || this._custom_properties.get(name)
    }
    /** List all stat names (connected and custom). */
    public ListStatNames(): string[] {
        const names = [] as string[]
        this._stats.forEach((_, key) => names.push(key))
        this._custom_stats.forEach((_, key) => names.push(key))
        return names
    }
    /** List all property names (connected and custom). */
    public ListPropertyNames(): string[] {
        const names = [] as string[]
        this._properties.forEach((_, key) => names.push(key))
        this._custom_properties.forEach((_, key) => names.push(key))
        return names
    }

    /**
     * Non-blocking replication readiness hook. If already ready, callback is called deferred.
     */
    public onReplicationReady(callback: () => void): void {
        if (this.replication_done) {
            task.defer(callback)
            return
        }
        this.janitor.Add(this.ReplicationReady.Connect(callback))
    }

    // PUBLIC: DESTROY
    /**
     * Dispose this character and unregister from global map.
     */
    public Destroy(): void {
        Character.CharacterRemoved.Fire(this)
        Character.CharactersMap.delete(this.instance)
        Character.CharactersById.delete(this.id)
    }
    
    // @internal //
    //STATUS EFFECTS

    // !! Dont use directly (internal) !! ---
    private _compound_effect_only_apply_effect(applied_effect: AppliedCompoundEffect) {
        this._effects.push(applied_effect)
        this.EffectApplied.Fire(applied_effect)

        applied_effect.janitor.Add(applied_effect.state.StateChanged.Connect(() => {
            this._handle_effects()
        }))
    }
    private _compound_effect_only_remove_effect(find_from: string | number): AppliedCompoundEffect | undefined {
        const effect = type(find_from) === "string"? this.GetAppliedEffectFromName(find_from as string) : this.GetAppliedEffectFromId(find_from as number)
        this._effects.forEach((val, index) => {
            if (val === effect) {
                this.EffectRemoved.Fire(effect)
                this._effects.remove(index)
            }
        })
        return effect
    }
    // ^^^ Dont use directly (internal) ^^^

    /**
     * Subscribe to all signals that may affect effects, and recompute on change.
     */
    private _start_listen_to_effect_changes(): void {
        const listen_to: Signal[] = [
            this.EffectApplied,
            this.EffectRemoved,
            this._effect_changed
        ]
        listen_to.forEach((signal) => {
            this.janitor.Add(signal.Connect(() => {
                this._handle_effects()
            }))
        })
    }

    /**
     * Rebuild flat effect lists from currently applied compound effects.
     */
    private _update_effects_maps(): void {
        const effects = this.GetAppliedEffectsMap()

        this._stat_effects.clear()
        this._property_effects.clear()

        effects.forEach((effect) => {
            if (effect.state.GetState() === "Ended") return

            effect.StatEffects.forEach((stat_effect) => {
                this._stat_effects.push(stat_effect)
            })
            effect.PropertyEffects.forEach((property_effect) => {
                this._property_effects.push(property_effect)
            })
        })
    }

    /**
     * Combine property effects by highest priority per affected property.
     */
    private _calculate_property_effects() {
        const calculated = new Map<string, {Affects: string, Strength: unknown, Priority: number}>()

        this._property_effects.forEach((effect) => {
            if (effect.state.GetState() !== "On") {
                return
            }
            
            let member = calculated.get(effect.Affects) || {
                    Affects: effect.Affects,
                    Strength: effect.Strength,
                    Priority: effect.Priority || 1
                }

            if (effect.Priority && 1 > member.Priority) {
                member.Priority = effect.Priority || 1
                member.Strength = effect.Strength
            }

            calculated.set(member.Affects, member)
        })

        return calculated as Map<string, {Affects: string, Strength: unknown, Priority: number}>
    }
    /**
     * Accumulate stat effects into raw and modifier components per affected stat.
     */
    private _calculate_stat_effects() {
        const calculated = new Map<string, {Affects: string, Raw: number, Modifier: number}>()

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
                    Modifier: 1
                }
            }

            if (effect_type === "Modifier") {
                member.Modifier = member.Modifier * effect.Strength
            } else if (effect_type === "Raw") {
                member.Raw = member.Raw + effect.Strength
            } else {
                 log.e(effect + " have wrong effect type property! /n Should be 'Raw' or 'Modifier' but have value of: " + effect.EffectType)
            }

            calculated.set(member.Affects, member)
        })

        return calculated
    }

    /**
     * Apply calculated stat effects to both connected and custom stats.
     */
    private _update_stats(): void {
        const calculated = this._calculate_stat_effects()

        //return stats to base values
        const _return_to_base_value = (stat: _every_possible_stats_type) => {
            if (calculated.has(stat.name)) return
            stat.Bonus.Modifier.Set(1)
            stat.Bonus.Raw.Set(0)

        }
        this._stats.forEach(_return_to_base_value)
        this._custom_stats.forEach(_return_to_base_value)

        calculated.forEach((stat, key) => {
            let stat_to_affect
            stat_to_affect = this._stats.get(stat.Affects) || this._custom_stats.get(stat.Affects)
            if (stat_to_affect) {
                //stat to affect is innate stat
                stat_to_affect.Bonus.Modifier.Set(stat.Modifier)
                 stat_to_affect.Bonus.Raw.Set(stat.Raw)               
            } else {
                log.e(stat + " Cant affect any of stats becuase theres no stat with name: " + stat.Affects)
            } 
        })
    }
    /**
     * Apply calculated property effects to both connected and custom properties.
     */
    private _update_properties(): void {
        const calculated = this._calculate_property_effects()

        const _return_to_base_value = (property: _every_possible_properties_type) => {
            if (calculated.has(property.name)) return
            property.Reset()
        }

        this._properties.forEach(_return_to_base_value)
        this._custom_properties.forEach(_return_to_base_value)

        calculated.forEach((prop) => {
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
                        log.e(prop + " Have wrong Strength value! /n Cant assign " + typeOf(prop.Strength) + " to " + typeOf(prop_to_affect.Get()))
                    }
                } else {
                    log.e(prop + " Cant affect any of properties becuase theres no property with name: " + prop.Affects)
                }
            }
        })
    }

    //REPLICATION
    /**
     * Push this character's replicated info into the server-side atom.
     */
    private _update_server_atom(): void {
        const server = get_handler() as Server
        server.atom((state) => {
            const new_state = table.clone(state)
            new_state.set(this.instance, this.GetCharacterInfo())
            return new_state
        })
    }

    /**
     * Re-publish server atom whenever character-related signals change.
     */
    private _connect_server_atom_updating(): void {
        const signals = [
            this.EffectApplied,
            this.EffectRemoved,
            this.SkillAdded,
            this.SkillRemoved
        ]

        signals.forEach((signal) => {
            this.janitor.Add(signal.Connect(() => {
                this._update_server_atom()
            }))
        })
    }

    //Should be called only on client
    /**
     * Client-only helper to mirror a compound effect by name, returns disposer.
     */
    private _replicate_compound_effect(name: string) {
        const wthrow = (reason: string) => log.w(name + "CompoundEffect Replication failed. " + reason)

        if (!is_client_context()) {
            wthrow("Cant call Replication on Server!")
        }

        const effect = GetCompoundEffectFromName(name)
        if (!effect) {
            wthrow("Cant find CompoundEffect with name " + name)
            return
        }

        const applied_effect = effect.ApplyTo(this)

        return () => {applied_effect?.End()}
    }

    /**
     * Initialize server-side replication and mark when client acknowledges.
     */
    private _server_replication(): void {
        const server = get_handler() as Server
        if (!server) log.e("Server not found! Maybe you forgot to Create it?")
        
        this._connect_server_atom_updating()
        this._update_server_atom()

        if (this.player) {
            this.janitor.Add(ServerEvents.character_replication_done.connect(() => {
                this.replication_done = true
                this.ReplicationReady.Fire()
            }))
        } else {
            this.replication_done = true
            this.ReplicationReady.Fire()
        }

        dlog.l("Server-Side Character was successfully created for " + this.instance.Name)
    }
    /**
     * Initialize client-side replication observers for this character.
     */
    private _client_replication(): void {
        if (!this.player) return
        const client = get_handler() as Client
        if (!client) {log.e("Client not found! Maybe you forgot to Create it?")}

        observe(
            () => client_atom()?.compound_effects || new Map<string, CompoundEffectInfo>(),
            (_, key) => this._replicate_compound_effect(key)
        )

        dlog.l("Client-Side Character was successfully created for " + this.instance.Name)
        
        ClientEvents.character_replication_done.fire()
        // On client, replication is effectively ready immediately for local character
        this.ReplicationReady.Fire()
    }
    private _start_replication(): void {
        is_client_context()? this._client_replication() : this._server_replication()
    }

    //MAIN
    /**
     * Recompute effect-derived state and push to stats/properties.
     */
    private _handle_effects(): void {
        this._update_effects_maps()
        this._update_stats()
        this._update_properties()
    }

    /**
     * Lifecycle bootstrap for replication and effect observers.
     */
    private init(): boolean {
        this._start_replication()
         while(!this.replication_done && !is_client_context()) {task.wait()} // yield until replciation is done
        this._start_listen_to_effect_changes()
        return true
    }
}