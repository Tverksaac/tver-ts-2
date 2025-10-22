import Signal from "@rbxts/signal"
import { Timer } from "@rbxts/timer"
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

    public readonly timer = new Timer(1)
    public readonly state = new StateMachine<[EffectState]>

    protected OnClientStart?: () => void = () => {}
    protected OnServerStart?: () => void = () => {}
    protected OnClientEnd?: () => void = () => {}
    protected OnServerEnd?: () => void = () => {}

    public readonly Changed = new Signal<(effect: Effect, args: unknown) => void>()

    private readonly _janitor = new Janitor()

    constructor () {
        this.init()
    }

    public GetTimeLeft() {
        return this.timer.getTimeLeft()
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

        this.timer.setLength(duration)
        this.timer.start()
    }
    public Resume() {
        if (!this.IsActive()) {
            log.w(this.Name + " is not active, cant resume!")
            return
        }

        this.state.SetState("On")
        
        this.timer.resume()
    }
    public Stop() {
        if (!this.IsActive()) {
            log.w(this.Name + "is not active, cant be stopped!")
            return
        }

        this.state.SetState("Off")

        this.timer.pause()
    }
    public End() {
        if (!this.IsActive()) {
            return
        }

        this.state.SetState("Ended")

        if (this.timer.getTimeLeft() > 0) {
            this.timer.stop()
        }
    }

    public Destroy() {
        this.timer.destroy()
        this.state.Destroy()
        this.Changed.Destroy()
        print(this._janitor)
        this._janitor.Cleanup()
    }

    private _listen_for_changes() {
        const listen_for = [
            this.state.StateChanged,
        ]
        listen_for.forEach((signal) => {
            this._janitor.Add(
                signal.Connect((...args) => {
                    this.Changed.Fire(this, args)
                })
            )
        })
    }
    private _listen_for_timer() {
        const connection = 
        this.timer.completed.Connect(() => {
            this.End()
        })
        this._janitor.Add(
            () => connection.Disconnect()
        )
    }

    private init() {
        this.state.SetState("Ready")
        
        this._listen_for_changes()
        this._listen_for_timer()
    }
}