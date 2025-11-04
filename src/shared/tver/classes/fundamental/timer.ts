import { Janitor } from "@rbxts/janitor";
import { StateMachine } from "./state_machine";
import Signal from "@rbxts/signal";
import { TimerState } from "shared/tver/utility/_ts_only/types";
import { RunService } from "@rbxts/services";

/**
 * Simple heartbeat-driven timer with pause/resume and second ticks.
 */
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

    /** Get configured length in seconds. */
    public GetLength(): number {
        return this._length
    }
    /** Set the timer length (also resets time left). */
    public SetLength(to: number): void {
        this._length = to
        this._time_left = to
    }
    public ExtendDuration(to: number): void {
        this._time_left = this._time_left + to
    }
    public GetState(): TimerState | undefined {
        return this._state.GetState()
    }
    /** Current remaining time in seconds. */
    public GetTimeLeft(): number {
        return this._time_left
    }
    /** Unix timestamp at which the timer will end, based on current time left. */
    public GetEndTimestamp(): number {
        return DateTime.now().UnixTimestamp + this._time_left
    }
    /** Start or restart the timer from its length. */
    public Start(): void {
        if (this._state.GetState() === "Running") return
        this._time_left = this._length
        this._state.SetState("Running")
        this._run_thread = coroutine.create(() => {
            this.janitor.Add(this._run_connection = RunService.Heartbeat.Connect((dt) => {
                if (this._state.GetState() !== "Running") return
                this._time_left = this._time_left - dt
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
    /** Pause the timer without clearing remaining time. */
    public Pause(): void {
        if (this._state.GetState() !== "Running") return
        this._state.SetState("Paused")
        this.Paused.Fire()
    }
    /** Resume the timer if paused. */
    public Resume(): void {
        if (this._state.GetState() !== "Paused") return
        this._state.SetState("Running")
        this.Resumed.Fire()
    }
    /** Force-end the timer; disconnects heartbeat and fires Ended. */
    public End(): void {
        this._run_connection?.Disconnect()
        this._run_thread? coroutine.close(this._run_thread): undefined
        this._time_left = 0
        this._state.SetState("Ready")
        this.Ended.Fire()
    }

    /** Cleanup timer resources. */
    public Destroy(): void {
        this._run_connection?.Disconnect()
        this._run_thread? coroutine.close(this._run_thread): undefined
        this.janitor.Destroy()
    }
}