import Signal from "@rbxts/signal"
import { Timer } from "../fundamental/timer"
import { EffectState } from "shared/tver/utility/_ts_only/types"
import { StateMachine } from "../fundamental/state_machine"
import { Janitor } from "@rbxts/janitor"
import { get_logger } from "shared/tver/utility/utils"

const LOG_KEY = "[EFFECT]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

export abstract class Effect {
    public readonly Name = tostring(getmetatable(this))

    public abstract readonly Affects: unknown
    public abstract readonly Strength: unknown

    public readonly timer = new Timer()
    public readonly state = new StateMachine<[EffectState]>

    public readonly Changed = new Signal<(effect: Effect, args: unknown) => void>()

    private readonly janitor = new Janitor()

    constructor () {
        this.init()
    }

    public GetTimeLeft() {
        return this.timer.GetTimeLeft()
    }
    public IsActive() {
        return this.state.GetState() !== "Ended" && this.state.GetState() !== "Ready"
    }

    public Start(duration: number) {
        if (this.IsActive()) {
            log.w(this.Name + " already was started!")
            return
        }

        this.state.SetState("On")

        this.timer.SetLength(duration)
        this.timer.Start()
    }
    public Resume() {
        if (!this.IsActive()) {
            log.w(this.Name + " is not active, cant resume!")
            return
        }

        this.state.SetState("On")
        
        this.timer.Resume()
    }
    public Stop() {
        if (!this.IsActive()) {
            log.w(this.Name + "is not active, cant be stopped!")
            return
        }

        this.state.SetState("Off")

        this.timer.Pause()
    }
    public End() {
        if (!this.IsActive()) {
            return
        }

        this.state.SetState("Ended")

        if (this.timer.GetTimeLeft() > 0) {
            this.timer.End()
        }
    }

    public Destroy() {
        this.janitor.Cleanup()
        this.timer.Destroy()
        this.state.Destroy()
        this.Changed.Destroy()
    }

    private _listen_for_changes() {
        const listen_for = [
            this.state.StateChanged,
        ]
        listen_for.forEach((signal) => {
            this.janitor.Add(
                signal.Connect((...args) => {
                    this.Changed.Fire(this, args)
                })
            )
        })
    }
    private _listen_for_timer() {
        this.janitor.Add(this.timer.Ended.Connect(() => {
            this.End()
        }))
    }

    private init() {
        this.state.SetState("Ready")
        
        this._listen_for_changes()
        this._listen_for_timer()
    }
}