import Signal from "@rbxts/signal"
import { Timer } from "@rbxts/timer"
import { EffectState } from "shared/tver/utility/_ts_only/types"
import { StateMachine } from "./state_machine"

export abstract class Effect {
    public abstract readonly Affects: unknown
    public abstract readonly Duration: number
    public abstract readonly Strength: unknown

    private readonly _timer = new Timer(0)

    public readonly state = new StateMachine<[EffectState]>

    protected OnClientStart?: () => void = () => {}
    protected OnServerStart?: () => void = () => {}
    protected OnClientEnd?: () => void = () => {}
    protected OnServerEnd?: () => void = () => {}

    constructor () {}

    public GetTimeLeft() {
        return this._timer.getTimeLeft()
    }
    public IsActive() {
        return this.state.GetState() !== "Ended" && this.state.GetState() !== "Ready"
    }

    public Start() {
        if (this.IsActive()) {
            warn(this + " already was started!")
            return
        }

        this.state.SetState("On")

        this._timer.setLength(this.Duration)
        this._timer.start()
    }
    public Resume() {
        if (!this.IsActive()) {
            warn(this + " is not active, cant resume!")
            return
        }

        this.state.SetState("On")

        this._timer.resume()
    }
    public Stop() {
        if (!this.IsActive()) {
            warn(this + "is not active, cant be stopped!")
            return
        }

        this.state.SetState("Off")

        this._timer.pause()
    }
    public End() {
        if (!this.IsActive()) {
            warn(this + " is not active, cant end!")
        }

        this.state.SetState("Ended")

        this._timer.stop()
    }
}