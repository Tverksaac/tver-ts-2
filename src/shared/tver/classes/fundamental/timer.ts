import { Janitor } from "@rbxts/janitor";
import { StateMachine } from "./state_machine";
import Signal from "@rbxts/signal";
import { TimerState } from "shared/tver/utility/_ts_only/types";
import { RunService } from "@rbxts/services";

export class Timer {
    public Started = new Signal()
    public Paused = new Signal()
    public Resumed = new Signal()
    public Ended = new Signal()
    public SecondReached = new Signal<(second: number) => void>()

    private _length: number = 0
    private _time_left: number = 0
    private _state = new StateMachine<[TimerState]>()
    private janitor = new Janitor()
    private _run_thread: thread | undefined
    private _run_connection: RBXScriptConnection | undefined

    private _last_second: number = -1

    constructor () {}

    public GetLength() {
        return this._length
    }
    public SetLength(to: number) {
        this._length = to
        this._time_left = to
    }
    public GetState(): TimerState | undefined {
        return this._state.GetState()
    }
    public GetTimeLeft(): number {
        return this._time_left
    }
    public GetEndTimestamp(): number {
        return DateTime.now().UnixTimestamp + this._time_left
    }
    public Start() {
        this._time_left = this._length
        this._run_thread = coroutine.create(() => {
            this.janitor.Add(this._run_connection = RunService.Heartbeat.Connect((dt) => {
                if (this._state.GetState() === "Paused") return
                this._time_left -= dt
                if (this._time_left <= 0) {
                    this.End()
                }
                const ceiled = math.ceil(this._time_left)
                if (ceiled !== this._last_second) {
                    this._last_second = ceiled
                    this.SecondReached.Fire(ceiled)
                }
            }))
        })
        coroutine.resume(this._run_thread)
        this.Started.Fire()
    }
    public Pause() {
        this._state.SetState("Paused")
        this.Paused.Fire()
    }
    public Resume() {
        this._state.SetState("Running")
        this.Resumed.Fire()
    }
    public End() {
        print('ending')
        this._run_connection?.Disconnect()
        this._run_thread? coroutine.close(this._run_thread): undefined
        this.Ended.Fire()
    }

    public Destroy() {
        this.janitor.Destroy()
    }
}