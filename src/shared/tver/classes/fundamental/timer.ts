import { Janitor } from "@rbxts/janitor";
import { StateMachine } from "./state_machine";
import Signal from "@rbxts/signal";

export class Timer {

    private _length: number
    private _state = new StateMachine<["Ready", "Running", "Paused"]>()
    private _janitor = new Janitor()
    private _run_thread: thread | undefined

    public Started = new Signal()
    public Paused = new Signal()
    public Resumed = new Signal()
    public Ended = new Signal()
    public SecondReached = new Signal()

    constructor (length = 1) {
        this._length = length
    }

    public GetLength() {
        return this._length
    }
    public SetLength() {}
    public GetState() {}
    public GetTimeLeft() {}
    public GetEndTimestamp() {}
    public Start() {}
    public Pause() {}
    public Resume() {}
    public End() {}
}