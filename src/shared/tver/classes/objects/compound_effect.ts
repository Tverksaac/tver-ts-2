import { Effect } from "../core/effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../core/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../core/stat_effect"
import { Character } from "./character";
import { EffectState } from "shared/tver/utility/_ts_only/types";
import { StateMachine } from "../fundamental/state_machine";
import { get_context_name, get_id, get_logger, is_client_context, wlog } from "shared/tver/utility/utils";
import { Constructor } from "@flamework/core/out/utility";
import { Janitor } from "@rbxts/janitor";
import Signal from "@rbxts/signal";
import { Timer } from "../fundamental/timer";

const LOG_KEY = "[COMP_EFFECT]"

const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

/**
 * Global registry for `CompoundEffect` classes and instances.
 */
class Container_CompoundEffect {
    public static readonly RegisteredCompoundEffects = new Map<string, CompoundEffect>()

    /**
     * Register a `CompoundEffect` class by constructor.
     */
    public static Register<T extends CompoundEffect>(Effect: Constructor<T>) {
        const name = tostring(Effect)
        if (this.RegisteredCompoundEffects.has(name)) {wlog(Effect + " already registered"); return}
        this.RegisteredCompoundEffects.set(name, new Effect())
    }
    /**
     * Get a registered effect instance by its name.
     */
    public static GetFromName(name: string): CompoundEffect | undefined {
        return this.RegisteredCompoundEffects.get(name)
    }
    /**
     * Get a registered effect instance by its constructor.
     */
    public static GetFromConstructor<T extends CompoundEffect>(Constructor: Constructor<T>): T | undefined {
        return this.RegisteredCompoundEffects.get(tostring(Constructor)) as T
    }
}

/**
 * Base class for a set of stat/property effects that act together.
 */
export abstract class CompoundEffect {
    public readonly Name = tostring(getmetatable(this))

    public readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[]= []
    public readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[] = []

    public Stackable = false
    public StartOnApply = true

    public OnStartServer() {}
    public OnStartClient() {}

    public OnResumeServer() {}
    public OnResumeClient() {}

    public OnPauseServer() {}
    public OnPauseClient() {}
    
    public OnEndServer() {}
    public OnEndClient() {}

    /**
     * Apply this effect to a `Character` with optional duration (<=0 means infinite).
     */
    public ApplyTo(to: Character, duration = -1): AppliedCompoundEffect {
        let effect = to.GetAppliedEffectFromName(this.Name)
        if (effect) {
            effect.SetDuration(duration < 0? math.huge : duration)
        } else {
            effect = new AppliedCompoundEffect(this, to, duration)
        }
        return effect
    }

    /**
     * Cleanup child effects.
     */
    public Destroy(): void {
        this.StatEffects.forEach((val) => {
            val.Destroy()
        })
        this.PropertyEffects.forEach((val) => [
            val.Destroy()
        ])
    }
}


/**
 * A live instance of a `CompoundEffect` applied to a carrier character.
 */
export class AppliedCompoundEffect extends CompoundEffect{
    public readonly Name: string

    public Duration: number;
    public StatEffects: (StrictStatEffect<never> | CustomStatEffect)[];
    public PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[];

    public Started = new Signal()
    public Resumed = new Signal()
    public Paused = new Signal()
    public Ended = new Signal()
    public Destroying = new Signal()

    public readonly state = new StateMachine<[EffectState]>()
    public readonly timer = new Timer()
    public readonly id = get_id()

    public readonly InheritsFrom: CompoundEffect
    public readonly Carrier: Character
    public readonly janitor = new Janitor()

    private _main_thread: thread | undefined
    private _msic_thread: thread | undefined

    constructor (from: CompoundEffect, to: Character, duration: number) {
        super()
        this.InheritsFrom = from
        this.Carrier = to
        this.Name = tostring(getmetatable(this.InheritsFrom))

        this.Duration = duration < 0? math.huge : duration
        this.StatEffects = from.StatEffects
        this.PropertyEffects = from.PropertyEffects

        // Copy callbacks from the source instance (delegation)
        this.OnStartServer = from.OnStartServer
        this.OnEndServer = from.OnEndServer
        this.OnStartClient = from.OnStartClient
        this.OnEndClient = from.OnEndClient
        this.OnPauseClient = from.OnPauseClient
        this.OnPauseServer = from.OnPauseServer
        this.OnResumeClient = from.OnResumeClient
        this.OnResumeServer = from.OnResumeServer

        this.ApplyTo = () => {
            wlog("Cant call :ApplyTo on AppliedStatusEffect!")
            return this
        }

        this.init()
        to._manipulate._apply_effect(this)

        if (this.StartOnApply) {
            this.Start()
        }
    }

    /**
     * Increase remaining duration by the provided amount.
     */
    public ExtendDuration(to: number): void {
        this.timer.SetLength(this.timer.GetTimeLeft() + to)
        this.for_each_effect((effect) => {
            effect.timer.SetLength(effect.GetTimeLeft() + to)
        })
    }
    /**
     * Set a new absolute duration for the effect and children.
     */
    public SetDuration(to: number): void {
        this.timer.SetLength(to)
        this.for_each_effect((effect) => {
            effect.timer.SetLength(to)
        })
    }

    /**
     * Start the effect; transitions state to On and starts timers.
     */
    public Start(): void {
        if (this.state.GetState() !== "Ready") {
            log.w(this.Name + " Effect cant be started twice!")
            return
        }
        this.timer.SetLength(this.Duration) // update length
        this.timer.Start()
        this.for_each_effect((effect) => {
            effect.Start(this.Duration)
        })
        
        this.for_each_effect_included((effect) => {
            effect.state.SetState("On")
        })

        this.Started.Fire()
    }
    /**
     * Resume a paused effect.
     */
    public Resume(): void {
        if (this.state.GetState() === "Ended") {
            log.w(this.Name + " is already ended!")
            return
        }
        this.timer.Resume()
        this.for_each_effect((effect) => {
            effect.Resume()
        })
        
        this.for_each_effect_included((effect) => {
            effect.state.SetState("On")
        })

        this.Resumed.Fire()
    }
    /**
     * Pause the running effect.
     */
    public Pause(): void {
        if (this.state.GetState() === "Ended") {
            log.w(this.Name + " is already ended!")
            return
        }
        this.timer.Pause()
        this.for_each_effect((effect) => {
            effect.Stop()
        })
        
        this.for_each_effect_included((effect) => {
            effect.state.SetState("Off")
        })

        this.Paused.Fire()
    }
    /**
     * End the effect and clean up child effects.
     */
    public End(): void {
        if (this.state.GetState() === "Ended") {
            return
        }

        if (this.timer.GetTimeLeft() > 0) this.timer.End() // stop timer if still going

        //end all effects
        this.for_each_effect((effect) => {
            effect.End()
        })

        this.Carrier?._manipulate._remove_effect(this.id) // remove effect from carrier

        this.for_each_effect_included((effect) => {
            effect.state.SetState("Ended")
        })
        
        this.Ended.Fire()
    }
    /**
     * Destroy this instance and release resources.
     */
    public Destroy(): void {
        dlog.w("Destroying: " + this.Name + " On " + get_context_name())
        this.Destroying.Fire()
        if (this.state.GetState() !== "Ended") {this.End()}

        this.for_each_effect((effect) => {
            effect.Destroy()
        })

        this.janitor.Destroy()
    }
    
    private for_each_effect(callback: (effect: Effect) => void): void {
        this.StatEffects.forEach(callback)
        this.PropertyEffects.forEach(callback)
    }
    private for_each_effect_included(callback: (effect: Effect | AppliedCompoundEffect) => void): void {
        this.for_each_effect(callback)
        callback(this)
    }
    private _listen_for_timer(): void {
        const connection =
        this.janitor.Add(this.timer.Ended.Connect(() => {
            this.Destroy()
        }))

        this.janitor.Add(
            () => connection.Disconnect()
        )
    }
    private _handle_callbacks(): void {
        const state = this.state.GetState()
        const prev_state = this.state.GetPreviousState()
        if (state === "On") {
            if (prev_state === "Ready") {
                //Effect Started
                this._main_thread = coroutine.create(() => {
                    is_client_context()? this.OnStartClient() : this.OnStartServer()
                })
                coroutine.resume(this._main_thread)
            }
            else if (prev_state === "Off") {
                //Effect Resumed
                this._main_thread = coroutine.create(() => {
                    is_client_context()? this.OnStartClient() : this.OnStartServer()
                })
                this._msic_thread = coroutine.create(() => {
                    is_client_context()? this.OnResumeClient() : this.OnResumeServer()
                })
                coroutine.resume(this._main_thread)
                coroutine.resume(this._msic_thread)
            }
        }
        else if (state === "Off") {
            //Effect Paused
            this._main_thread? coroutine.close(this._main_thread): undefined
            this._msic_thread? coroutine.close(this._msic_thread): undefined
            this._msic_thread = coroutine.create(() => {
                is_client_context()? this.OnPauseClient() : this.OnPauseServer()
            })
            coroutine.resume(this._msic_thread)
        }
        else if (state === "Ended") {
            //Effect ended
            this._msic_thread? coroutine.close(this._msic_thread): undefined
            this._main_thread? coroutine.close(this._main_thread): undefined
            is_client_context()? this.OnEndClient() : this.OnEndServer() // Yields!
        }
    }
    private init(): void {
        this.for_each_effect_included((effect) => {
            effect.state.SetState("Ready")
        })

        this.janitor.Add(this.state.StateChanged.Connect(() => this._handle_callbacks()))

        this._listen_for_timer()
    }
}

export function GetCompoundEffectFromConstructor<T extends CompoundEffect>(Constructor: Constructor<T>): T | undefined {
    return Container_CompoundEffect.GetFromConstructor<T>(Constructor)
}
export function GetCompoundEffectFromName(Name: string): CompoundEffect | undefined {
    return Container_CompoundEffect.GetFromName(Name)
}
export function Decorator_CompoundEffect<T extends CompoundEffect>(Constructor: Constructor<T>): void {
    Container_CompoundEffect.Register(Constructor)
}