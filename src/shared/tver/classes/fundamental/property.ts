//!native

import { Janitor } from "@rbxts/janitor";
import { RunService } from "@rbxts/services";
import Signal from "@rbxts/signal";
import { get_context_name, get_logger, is_client_context } from "shared/tver/utility/utils";

const LOG_KEY = "[PROPERTY]"
const CONNECTED_TAG = "[TVER]" + LOG_KEY
const dlog = get_logger(LOG_KEY, true)

function create_tag(name: string): string {
	return CONNECTED_TAG + (`[${string.upper(get_context_name())}]`) + " Connected to " + name
}


/**
 * Property that maintains its own value and change notifications (not bound to an Instance).
 */
export class SeparatedProperty<T> {
	protected janitor = new Janitor()

	public readonly name: string;
	protected value: T;
	protected default_value: T;

	public changed = new Signal<(new_value: T, prev_value: T) => void>()

	Behaviours: {
		OnTick: (this: void) => void;
		OnChanged: (this: void, new_value: unknown, old_value: unknown) => void;
		CanSet: (this: void) => boolean;
	};

	constructor(name: string, value: T) {
		this.name = name;
		this.value = value;
		this.default_value = value

		this.Behaviours = {
			OnTick() {},
			OnChanged(new_value, old_value) {},
			CanSet() {
				return true;
			},
		};

		this.janitor.Add(
			this.changed.Connect((new_value, old_value) => {
				this.Behaviours.OnChanged(new_value, old_value);
			}),
		);
		this.janitor.Add(
			RunService.Heartbeat.Connect(() => {
				this.Behaviours.OnTick();
			}),
		);
	}

	/** Set the property value. Returns true if value changed or was set. */
	Set(set_to: T, silent = false): boolean {
		if (!this.Behaviours.CanSet()) {
			return false;
		}
		if (this.value === set_to) {
			return true;
		}
		const old_value = this.value;
		this.value = set_to;
		if (!silent) {
			this.changed.Fire(set_to, old_value);
		}
		return true;
	}

	SetDefault(set_to: T) {
		this.default_value = set_to
	}

	/** Get the current property value. */
	Get(): T {
		return this.value;
	}

	/** Reset the property back to its default value. */
	Reset(): void {
		this.Set(this.default_value)
	}

	/** Cleanup any connections/resources. */
	Destroy(): void {
		this.janitor.Destroy();
	}
}

/**
 * Property bound to an Instance's property with optional override behavior.
 */
export class ConnectedProperty<
	ConnectedInstance extends Instance,
	Name extends keyof WritableInstanceProperties<ConnectedInstance>,
> extends SeparatedProperty<ConnectedInstance[Name]> {
	connected_to: Name;
	instance: ConnectedInstance;
	override: boolean;

	constructor(
		ConnectToInstance: ConnectedInstance,
		Name: Name,
		Value: ConnectedInstance[Name],
		Override = true,
		CanBeCreatedOnClient = false
	) {
		super(tostring(Name), Value);
		this.instance = ConnectToInstance;
		this.instance[Name] = this.value;
		this.connected_to = Name;
		this.override = Override;

		const tag = create_tag(tostring(Name))
		if (ConnectToInstance.HasTag(tag)) {
			this.Destroy()
			return
		} else {
			ConnectToInstance.AddTag(tag)
		}

		if (is_client_context() && !CanBeCreatedOnClient) return
		this.janitor.Add(
			this.changed.Connect((new_value: ConnectedInstance[Name]) => {
				this.instance[Name] = new_value;
			}),
		);
		this.janitor.Add(
			this.instance.GetPropertyChangedSignal<ConnectedInstance>(Name).Connect(() => {
				if (!this.override) {
					this.Set(this.instance[Name]);
				} else {
					this.instance[Name] = this.Get();
				}
			}),
		);
	}
	
	public getType(): string {
		return "ConnectedProperty"
	}
}
