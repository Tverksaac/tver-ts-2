import { Effect } from "../core/effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../core/property_effect"
import {CustomStatEffect, StrictStatEffect } from "../core/stat_effect"
import { Character } from "./character";
import { EffectState } from "shared/tver/utility/_ts_only/types";
import { StateMachine } from "../fundamental/state_machine";
import { get_id, get_logger, is_client_context, wlog } from "shared/tver/utility/utils";
import { Constructor } from "@flamework/core/out/utility";
import { Timer } from "@rbxts/timer";
import { Janitor } from "@rbxts/janitor";

const LOG_KEY = "[COMP_EFFECT]"

const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

export class Container_CompoundEffect {
    public static readonly RegisteredCompoundEffects = new Map<string, CompoundEffect>()

    public static Register<T extends CompoundEffect>(Effect: Constructor<T>) {
        const effect = new Effect()
        const name = tostring(Effect)
        if (this.RegisteredCompoundEffects.has(name)) {wlog(Effect + " Already was registred!"); return}
        this.RegisteredCompoundEffects.set(name, effect)
    }
    public static GetCompoundEffectFromName(name: string): CompoundEffect | undefined {
        return this.RegisteredCompoundEffects.get(name)
    }
    public static GetCompoundEffectFromConstructor<T extends CompoundEffect>(Constructor: Constructor<T>): CompoundEffect | undefined {
        return this.RegisteredCompoundEffects.get(tostring(Constructor))
    }
}

export class CompoundEffect {
    public readonly Name = tostring(getmetatable(this))

    public readonly StatEffects: (StrictStatEffect<never> | CustomStatEffect)[]= []
    public readonly PropertyEffects: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[] = []

    public StartOnApply = true

    protected OnStartServer() {}
    protected OnStartClient() {}

    protected OnResumeServer() {}
    protected OnResumeClient() {}

    protected OnPauseServer() {}
    protected OnPauseClient() {}
    
    protected OnEndServer() {}
    protected OnEndClient() {}

    public ApplyTo(to: Character, duration: number) {
        return new AppliedCompoundEffect(this, to, duration)
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

    public readonly state = new StateMachine<[EffectState]>()
    public readonly timer = new Timer(1)
    public readonly id = get_id()

    public readonly InheritsFrom: CompoundEffect
    public readonly CarrierID: number

    private readonly _janitor = new Janitor()

    constructor (from: CompoundEffect, to: Character, duration: number) {
        super()

        this.InheritsFrom = from
        this.CarrierID = to.id
        this.Name = tostring(getmetatable(this.InheritsFrom))

        this.Duration = duration
        this.StatEffects = table.clone(from.StatEffects)
        this.PropertyEffects = table.clone(from.PropertyEffects)

        this.ApplyTo = () => {
            wlog("Cant call :ApplyTo on AppliedStatusEffect!")
            return this
        }

        this.init()
        this.state.SetState("Ready")

        to._internal_apply_effect(this)

        if (this.StartOnApply) {
            this.Start()
        }
    }

    public ExtendDuration(to: number) {
        this.timer.setLength(this.timer.getTimeLeft() + to)
    }
    public SetDuration(to: number) {
        this.timer.setLength(to)
    }

    public Start() {
        if (this.state.GetState() !== "Ready") {
            warn(this.Name + " Effect cant be started twice!")
            return
        }
        
        this.state.SetState("On")

        this.timer.setLength(this.Duration)
        this.timer.start()

        this.for_each_effect((effect) => {
            effect.Start(this.Duration)
        })

        is_client_context() ? this.OnStartClient() : this.OnStartServer()
    }
    public Resume() {
        if (this.state.GetState() === "Ended") {
            warn(this.Name + " is already ended!")
            return
        }

        this.state.SetState("On")

        this.timer.resume()

        this.for_each_effect((effect) => {
            effect.Resume()
        })

        is_client_context() ? this.OnResumeClient() : this.OnResumeServer()
    }
    public Stop() {
        if (this.state.GetState() === "Ended") {
            warn(this.Name + " is already ended!")
            return
        }

        this.state.SetState("Off")

        this.timer.pause()

        this.for_each_effect((effect) => {
            effect.Stop()
        })

        is_client_context() ? this.OnPauseClient() : this.OnPauseServer()
    }
    public End() {
        if (this.state.GetState() === "Ended") {
            return
        }

        this.state.SetState("Ended") // change state
        if (this.timer.getTimeLeft() > 0) this.timer.stop() // stop timer if still going

        //end all effects
        this.for_each_effect((effect) => {
            effect.End()
        })

        const carrier = Character.GetCharacterFromId(this.CarrierID)
        carrier?._internal_remove_effect(this.id) // remove effect from carrier

        is_client_context()? this.OnEndClient() : this.OnEndServer()
    }
    public Destroy() {
        dlog.w("Destroying: " + this.Name)
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

        this.timer.secondReached.Connect((s) => print(s))
    }
    private init() {
        this._listen_for_timer()
    }
}

export function CompoundEffectDecorator<T extends CompoundEffect>(Constructor: Constructor<T>) {
    Container_CompoundEffect.Register(Constructor)
}