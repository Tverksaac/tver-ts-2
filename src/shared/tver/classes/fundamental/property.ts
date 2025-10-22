import { Janitor } from "@rbxts/janitor";
import { RunService } from "@rbxts/services";
import Signal from "@rbxts/signal";
import { get_logger, is_client_context } from "shared/tver/utility/utils";

const LOG_KEY = "[PROPERTY]"
const CONNECTED_TAG = "[TVER]" + LOG_KEY + " Connected to "
const dlog = get_logger(LOG_KEY, true)

export class SeparatedProperty<T> {
	protected _janitor = new Janitor()

	public readonly name: string;
	protected value: T;
	protected readonly defualt_value: T;

	public changed = new Signal<(new_value: T, prev_value: T) => void>()

	Behaviours: {
		OnTick: (this: void) => void;
		OnChanged: (this: void, new_value: unknown, old_value: unknown) => void;
		CanSet: (this: void) => boolean;
	};

	constructor(name: string, value: T) {
		this.name = name;
		this.value = value;
		this.defualt_value = value

		this.Behaviours = {
			OnTick() {},
			OnChanged(new_value, old_value) {},
			CanSet() {
				return true;
			},
		};

		this._janitor.Add(
			this.changed.Connect((new_value, old_value) => {
				this.Behaviours.OnChanged(new_value, old_value);
			}),
		);
		this._janitor.Add(
			RunService.Heartbeat.Connect(() => {
				this.Behaviours.OnTick();
			}),
		);
	}

	Set(set_to: T, silent = false) {
		if (this.Behaviours.CanSet()) {
			if (this.value === set_to) {
				return true;
			}
			this.value = set_to;
			if (!silent) this.changed.Fire(set_to, this.value);
			return true;
		} else {
			return false;
		}
	}

	Get() {
		return this.value;
	}

	Reset() {
		this.Set(this.defualt_value)
	}

	getType(): string {
		return "SeparatedProperty"
	}

	Destroy() {
		this._janitor.Destroy();
	}
}

export class ConnectedProperty<
	ConnectedInstance extends Instance,
	Name extends keyof WritableInstanceProperties<ConnectedInstance>,
> extends SeparatedProperty<ConnectedInstance[Name]> {
	connected_to: Name;
	instance: ConnectedInstance;
	override: boolean;

	constructor(
		Name: Name,
		Value: ConnectedInstance[Name],
		ConnectToInstance: ConnectedInstance,
		Override = true,
		CanBeCreatedOnClient = false
	) {
		super(tostring(Name), Value);
		this.instance = ConnectToInstance;
		this.instance[Name] = this.value;
		this.connected_to = Name;
		this.override = Override;

		if (ConnectToInstance.HasTag(CONNECTED_TAG + tostring(Name))) {
			this.Destroy()
			return
		} else {
			ConnectToInstance.AddTag(CONNECTED_TAG + tostring(Name))
		}

		if (is_client_context() && !CanBeCreatedOnClient) return
		this._janitor.Add(
			this.changed.Connect((new_value: ConnectedInstance[Name]) => {
				this.instance[Name] = new_value;
			}),
		);
		this._janitor.Add(
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
