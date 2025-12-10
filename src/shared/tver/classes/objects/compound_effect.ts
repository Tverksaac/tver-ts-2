import { Effect } from "../core/effect";
import { CustomPropertyEffect, StrictPropertyEffect } from "../core/property_effect";
import { CustomStatEffect, StrictStatEffect } from "../core/stat_effect";
import { Character } from "./character";
import {
	CompoundEffectGenericParams,
	CompoundEffectPropertyEffects,
	CompoundEffectStatEffects,
	EffectState,
	GetParamType,
} from "shared/tver/utility/_ts_only/types";
import { StateMachine } from "../fundamental/state_machine";
import { get_context_name, get_id, get_logger, is_client_context, wlog } from "shared/tver/utility/utils";
import { Constructor } from "@flamework/core/out/utility";
import { Janitor } from "@rbxts/janitor";
import Signal from "@rbxts/signal";
import { Timer } from "../fundamental/timer";
import { CompoundEffectInfo } from "shared/tver/utility/_ts_only/interfaces";
import { ServerEvents } from "shared/tver/network/networking";

const LOG_KEY = "[CEFFECT]";

const log = get_logger(LOG_KEY);
const dlog = get_logger(LOG_KEY, true);

/**
 * Global registry for `CompoundEffect` classes and instances.
 */
export class Container_CompoundEffect {
	public static readonly RegisteredCompoundEffects = new Map<string, Constructor<CompoundEffect>>();

	/**
	 * Register a `CompoundEffect` class by constructor.
	 */
	public static Register<T extends Constructor<CompoundEffect>>(Effect: T): void {
		const name = tostring(Effect);
		if (this.RegisteredCompoundEffects.has(name)) {
			log.w(Effect + " already registered");
			return;
		}
		this.RegisteredCompoundEffects.set(name, Effect);
	}
	/**
	 * Get a registered effect instance by its name.
	 */
	public static GetFromName(name: string): Constructor<CompoundEffect> | undefined {
		return this.RegisteredCompoundEffects.get(name);
	}
	/**
	 * Get a registered effect instance by its constructor.
	 */
	public static GetFromConstructor<T extends Constructor<CompoundEffect>>(Constructor: T): T | undefined {
		return this.RegisteredCompoundEffects.get(tostring(Constructor)) as T | undefined;
	}
}

/**
 * Base class for a set of stat/property effects that act together.
 */
export abstract class CompoundEffect<Params extends Partial<CompoundEffectGenericParams> = {}> {
	public readonly Name = tostring(getmetatable(this));

	public readonly StatEffects?: CompoundEffectStatEffects = [];
	public readonly PropertyEffects?: CompoundEffectPropertyEffects = [];

	public readonly ConstructorParams: GetParamType<Params, "ConstructorParams">;

	public readonly Stackable = false;

	public OnApplyingServer(applied: AppliedCompoundEffect<Params>) {}
	public OnApplyingClient(applied: AppliedCompoundEffect<Params>) {}

	public OnStartServer(...params: GetParamType<Params, "OnStart">) {}
	public OnStartClient(...params: GetParamType<Params, "OnStart">) {}

	public OnResumeServer(...params: GetParamType<Params, "OnResume">) {}
	public OnResumeClient(...params: GetParamType<Params, "OnResume">) {}

	public OnPauseServer(...params: GetParamType<Params, "OnPause">) {}
	public OnPauseClient(...params: GetParamType<Params, "OnPause">) {}

	public OnAbortServer(...params: GetParamType<Params, "OnAbort">) {}
	public OnAbortClient(...params: GetParamType<Params, "OnAbort">) {}

	public OnEndServer() {}
	public OnEndClient() {}

	public OnRemovingServer() {}
	public OnRemovingClient() {}

	constructor(...params: GetParamType<Params, "ConstructorParams">) {
		this.ConstructorParams = params;
	}

	/**
	 * Apply this effect to a `Character` with optional duration (<=0 means infinite).
	 */
	//Override
	public ApplyTo(to: Character, duration = -1, id?: number): AppliedCompoundEffect<Params> {
		let effect = to.GetAppliedEffectFromName(this.Name);
		if (effect) {
			effect.SetDuration(duration < 0 ? math.huge : duration);
		} else {
			effect = new AppliedCompoundEffect(this, to, duration, id);
		}
		return effect;
	}

	/**
	 * Cleanup child effects.
	 */
	public Destroy(): void {
		this.StatEffects?.forEach((val) => {
			val.Destroy();
		});
		this.PropertyEffects?.forEach((val) => {
			val.Destroy();
		});
	}
}

/**
 * A live instance of a `CompoundEffect` applied to a carrier character.
 */
export class AppliedCompoundEffect<
	Params extends Partial<CompoundEffectGenericParams> = {},
> extends CompoundEffect<Params> {
	public readonly Name: string;

	public Duration: number;
	public StatEffects?: (StrictStatEffect<never> | CustomStatEffect)[];
	public PropertyEffects?: (StrictPropertyEffect<never, never> | CustomPropertyEffect)[];

	public Started = new Signal();
	public Resumed = new Signal();
	public Paused = new Signal();
	public Ended = new Signal();
	public Destroying = new Signal();

	public readonly state = new StateMachine<[EffectState]>("Ready");
	public readonly timer = new Timer();
	public readonly id: number;

	public readonly InheritsFrom: CompoundEffect<Params>;
	public readonly Carrier: Character;
	public readonly janitor = new Janitor();

	public LastStartParams?: GetParamType<Params, "OnStart">;
	public LastResumeParams?: GetParamType<Params, "OnResume">;
	public LastPauseParams?: GetParamType<Params, "OnPause">;

	public _main_thread: thread | undefined;
	public _pause_thread: thread | undefined;
	public _resume_thread: thread | undefined;

	public RemoveOnEnd: boolean = true;

	constructor(from: CompoundEffect<Params>, to: Character, duration: number, id?: number) {
		super(...from.ConstructorParams);
		this.InheritsFrom = from;
		this.Carrier = to;
		this.Name = tostring(getmetatable(this.InheritsFrom));
		this.id = id ? id : get_id();

		this.Duration = duration < 0 ? math.huge : duration;
		this.StatEffects = from.StatEffects;
		this.PropertyEffects = from.PropertyEffects;

		// Copy callbacks from the source instance maybe try to find another way to do it later
		this.OnApplyingServer = from.OnApplyingServer;
		this.OnApplyingClient = from.OnApplyingClient;
		this.OnStartServer = from.OnStartServer;
		this.OnEndServer = from.OnEndServer;
		this.OnStartClient = from.OnStartClient;
		this.OnEndClient = from.OnEndClient;
		this.OnPauseClient = from.OnPauseClient;
		this.OnPauseServer = from.OnPauseServer;
		this.OnResumeClient = from.OnResumeClient;
		this.OnResumeServer = from.OnResumeServer;
		this.OnRemovingServer = from.OnRemovingServer;
		this.OnRemovingClient = from.OnRemovingClient;

		this.ApplyTo = () => {
			wlog("Cant call :ApplyTo on AppliedStatusEffect!");
			return this;
		};

		this.init();

		is_client_context() ? this.OnApplyingClient(this) : this.OnApplyingServer(this);
	}

	public GetInfo(): CompoundEffectInfo {
		return {
			id: this.id,
			carrier_id: this.Carrier.id,
			state: this.state.GetState() || "Ready",
			constructor_params: this.ConstructorParams,
			start_params: this.LastStartParams,
			resume_params: this.LastResumeParams,
			pause_params: this.LastPauseParams,
		};
	}

	/**
	 * Increase remaining duration by the provided amount.
	 */
	public ExtendDuration(to: number): void {
		this.for_each_effect_included((effect) => {
			effect.timer.ExtendDuration(to);
		});

		this.Duration = this.Duration + to;
	}
	/**
	 * Set a new absolute duration for the effect and children.
	 */
	public SetDuration(to: number): void {
		this.timer.SetLength(to);
		this.for_each_effect((effect) => {
			effect.timer.SetLength(to);
		});

		this.Duration = to;
	}

	/**
	 * Start the effect; transitions state to On and starts timers.
	 */
	public Start(...params: GetParamType<Params, "OnStart">): AppliedCompoundEffect<Params> {
		if (this.state.GetState() !== "Ready") {
			log.w(this.Name + " Effect cant be started twice!");
			return this;
		}

		this.LastStartParams = params;

		this.timer.SetLength(this.Duration); // update length
		this.timer.Start();
		this.for_each_effect((effect) => {
			effect.Start(this.Duration);
		});

		this.for_each_effect_included((effect) => {
			effect.state.SetState("On");
		});

		//Start coroutine
		this._main_thread = coroutine.create(() => {
			is_client_context() ? this.OnStartClient(...params) : this.OnStartServer(...params);
		});
		coroutine.resume(this._main_thread);

		this.Started.Fire();

		return this;
	}
	/**
	 * Resume a paused effect.
	 *
	 * Previous OnResume callback will be closed
	 */
	public Resume(...params: GetParamType<Params, "OnResume">): void {
		if (this.state.GetState() === "Ended") {
			log.w(this.Name + " is already ended!");
			return;
		}

		this.LastResumeParams = params;

		this.timer.Resume();
		this.for_each_effect((effect) => {
			effect.Resume();
		});

		this.for_each_effect_included((effect) => {
			effect.state.SetState("On");
		});

		this._resume_thread ? coroutine.close(this._resume_thread) : undefined;
		this._resume_thread = coroutine.create(() => {
			is_client_context() ? this.OnResumeClient(...params) : this.OnResumeServer(...params);
		});
		coroutine.resume(this._resume_thread);

		this.Resumed.Fire();
	}
	/**
	 * Pause the running effect.
	 *
	 * Previous pause thread will be closed
	 */
	public Pause(...params: GetParamType<Params, "OnPause">): void {
		if (this.state.GetState() === "Ended") {
			log.w(this.Name + " is already ended!");
			return;
		}

		this.timer.Pause();
		this.for_each_effect((effect) => {
			effect.Stop();
		});

		this.for_each_effect_included((effect) => {
			effect.state.SetState("Off");
		});

		this._pause_thread ? coroutine.close(this._pause_thread) : undefined;

		this._pause_thread = coroutine.create(() => {
			is_client_context() ? this.OnPauseClient(...params) : this.OnPauseServer(...params);
		});
		coroutine.resume(this._pause_thread);

		this.Paused.Fire();
	}
	/**
	 *
	 * Aborts the effect, it can be reused after abort, even if RemoveOnEnd == true
	 */
	public Abort(...params: GetParamType<Params, "OnAbort">) {}
	/**
	 * End the effect and clean up child effects.
	 */
	public End(): void {
		if (this.state.GetState() === "Ended") {
			return;
		}

		if (this.timer.GetTimeLeft() > 0) this.timer.End(); // stop timer if still going

		//end all effects
		this.for_each_effect((effect) => {
			effect.End();
		});

		this.Carrier?._manipulate._remove_effect(this.id); // remove effect from carrier

		this.for_each_effect_included((effect) => {
			effect.state.SetState(this.RemoveOnEnd ? "Ended" : "Ready");
		});

		this._pause_thread ? coroutine.close(this._pause_thread) : undefined;
		this._resume_thread ? coroutine.close(this._resume_thread) : undefined;
		this._main_thread ? coroutine.close(this._main_thread) : undefined;
		is_client_context() ? this.OnEndClient() : this.OnEndServer(); // Yields!

		this.Ended.Fire();

		if (this.RemoveOnEnd) {
			this.Remove();
		}
	}
	/**
	 * Destroy this instance and release resources.
	 */
	public Remove(): void {
		dlog.w("Destroying: " + this.Name + " On " + get_context_name());

		if (this.state.GetState() !== "Ended") {
			dlog.w("Cant remove ongoing effect!");
			return;
		}

		this.End();

		is_client_context() ? this.OnRemovingClient() : this.OnRemovingServer();

		this.janitor.Destroy();
		this.Destroy();
	}
	private for_each_effect(callback: (effect: Effect) => void): void {
		this.StatEffects?.forEach(callback);
		this.PropertyEffects?.forEach(callback);
	}
	private for_each_effect_included(callback: (effect: Effect | AppliedCompoundEffect<Params>) => void): void {
		this.for_each_effect(callback);
		callback(this);
	}
	private _listen_for_timer(): void {
		const connection = this.janitor.Add(
			this.timer.Ended.Connect(() => {
				this.End();
			}),
		);

		this.janitor.Add(() => connection.Disconnect());
	}
	private init(): void {
		this.for_each_effect_included((effect) => {
			effect.state.SetState("Ready");
		});

		//Init
		this._listen_for_timer();
		this.Carrier._manipulate._apply_effect(this);

		//Start syncing client-sided and server-sided effect
		if (!is_client_context() && this.Carrier.player) {
			this.janitor.Add(
				this.state.StateChanged.Connect(() => {
					ServerEvents.Manipulate.sync_compound_effect(this.Carrier.player as Player, this.GetInfo());
				}),
			);
		}
	}
}

export function Decorator_CompoundEffect<Params extends Partial<CompoundEffectGenericParams>>(
	Constructor: Constructor<CompoundEffect<Params>>,
): void {
	Container_CompoundEffect.Register(Constructor);
}
