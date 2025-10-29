import { Effect } from "../core/effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../core/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../core/stat_effect"
import { Character } from "./character";
import { EffectState } from "shared/tver/utility/_ts_only/types";
import { StateMachine } from "../fundamental/state_machine";
import { get_context_name, get_id, get_logger, is_client_context, wlog } from "shared/tver/utility/utils";
import { Constructor } from "@flamework/core/out/utility";
import { Timer } from "@rbxts/timer";
import { Janitor } from "@rbxts/janitor";
import Signal from "@rbxts/signal";

const LOG_KEY = "[COMP_EFFECT]"

const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

class Container_CompoundEffect {
    public static readonly RegisteredCompoundEffects = new Map<string, CompoundEffect>()

    public static Register<T extends CompoundEffect>(Effect: Constructor<T>) {
        const name = tostring(Effect)
        if (this.RegisteredCompoundEffects.has(name)) {wlog(Effect + " Already was registred!"); return}
        this.RegisteredCompoundEffects.set(name, new Effect())
    }
    public static GetFromName(name: string): CompoundEffect | undefined {
        return this.RegisteredCompoundEffects.get(name)
    }
    public static GetFromConstructor<T extends CompoundEffect>(Constructor: Constructor<T>): T | undefined {
        return this.RegisteredCompoundEffects.get(tostring(Constructor)) as T
    }
}

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

    public ApplyTo(to: Character, duration = -1): AppliedCompoundEffect {
        let effect = to.GetAppliedEffectFromName(this.Name)
        if (effect) {
            effect.SetDuration(duration < 0? math.huge : duration)
        } else {
            effect = new AppliedCompoundEffect(this, to, duration)
        }
        print(to)
        return effect
    }

    public Destroy() {
        this.StatEffects.forEach((val) => {
            val.Destroy()
        })
        this.PropertyEffects.forEach((val) => [
            val.Destroy()
        ])
    }
}


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
    public readonly timer = new Timer(1)
    public readonly id = get_id()

    public readonly InheritsFrom: CompoundEffect
    public readonly Carrier: Character

    private readonly _janitor = new Janitor()
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

        //Maybe find another way to do it later
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

    public ExtendDuration(to: number) {
        this.timer.setLength(this.timer.getTimeLeft() + to)
        this.for_each_effect((effect) => {
            effect.timer.setLength(effect.GetTimeLeft() + to)
        })
    }
    public SetDuration(to: number) {
        this.timer.setLength(to)
        this.for_each_effect((effect) => {
            effect.timer.setLength(to)
        })
    }

    public Start() {
        if (this.state.GetState() !== "Ready") {
            log.w(this.Name + " Effect cant be started twice!")
            return
        }
        this.timer.setLength(this.Duration) // update length
        this.timer.start()
        this.for_each_effect((effect) => {
            effect.Start(this.Duration)
        })
        this.state.SetState("On")
        this.Started.Fire()
    }
    public Resume() {
        if (this.state.GetState() === "Ended") {
            log.w(this.Name + " is already ended!")
            return
        }
        this.timer.resume()
        this.for_each_effect((effect) => {
            effect.Resume()
        })
        this.state.SetState("On")
        this.Resumed.Fire()
    }
    public Pause() {
        if (this.state.GetState() === "Ended") {
            log.w(this.Name + " is already ended!")
            return
        }
        this.timer.pause()
        this.for_each_effect((effect) => {
            effect.Stop()
        })
        this.state.SetState("Off")
        this.Paused.Fire()
    }
    public End() {
        if (this.state.GetState() === "Ended") {
            return
        }

        if (this.timer.getTimeLeft() > 0) this.timer.stop() // stop timer if still going

        //end all effects
        this.for_each_effect((effect) => {
            effect.End()
        })

        this.Carrier?._manipulate._remove_effect(this.id) // remove effect from carrier

        this.state.SetState("Ended") // change state
        this.Ended.Fire()
    }
    public Destroy() {
        dlog.w("Destroying: " + this.Name + " On " + get_context_name())
        this.Destroying.Fire()
        if (this.state.GetState() !== "Ended") {this.End()}

        this.for_each_effect((effect) => {
            effect.Destroy()
        })

        this._janitor.Destroy()
    }
    
    private for_each_effect(callback: (effect: Effect) => void) {
        this.StatEffects.forEach(callback)
        this.PropertyEffects.forEach(callback)
    }
    private _listen_for_timer() {
        const connection =
        this.timer.stopped.Connect(() => {
            this.Destroy()
        })

        this._janitor.Add(
            () => connection.Disconnect()
        )
    }
    private _handle_callbacks() {
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
    private init() {
        this.state.SetState("Ready")
        this.state.StateChanged.Connect(() => this._handle_callbacks())

        this._listen_for_timer()
    }
}

export function GetCompoundEffectFromConstructor<T extends CompoundEffect>(Constructor: Constructor<T>): T | undefined {
    return Container_CompoundEffect.GetFromConstructor<T>(Constructor)
}
export function GetCompoundEffectFromName(Name: string) {
    return Container_CompoundEffect.GetFromName(Name)
}
export function Decorator_CompoundEffect<T extends CompoundEffect>(Constructor: Constructor<T>) {
    Container_CompoundEffect.Register(Constructor)
}