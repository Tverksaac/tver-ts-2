import { Janitor } from "@rbxts/janitor";
import { RunService } from "@rbxts/services";

export class SeparatedProperty<T> {
	protected _janitor = new Janitor()

	readonly name: string;
	protected value: T;
	changed: RBXScriptSignal<Callback>;

	Behaviours: {
		OnTick: (this: void) => void;
		OnChanged: (this: void, new_value: unknown, old_value: unknown) => void;
		CanSet: (this: void) => boolean;
	};

	protected _changed_bind: BindableEvent<Callback>;

	constructor(name: string, value: T) {
		this.name = name;
		this.value = value;

		this._changed_bind = new Instance("BindableEvent");
		this.changed = this._changed_bind.Event;

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

	Set(set_to: T) {
		if (this.Behaviours.CanSet()) {
			if (this.value === set_to) {
				return true;
			}
			this._changed_bind.Fire(set_to, this.value);
			this.value = set_to;
			return true;
		} else {
			return false;
		}
	}

	Get() {
		return this.value;
	}

	Destroy() {
		this._janitor.Cleanup();
		this._janitor.Destroy();
	}
}

export class ConnectedProperty<
	Name extends keyof WritableInstanceProperties<ConnectedInstance>,
	ConnectedInstance extends Instance,
> extends SeparatedProperty<ConnectedInstance[Name]> {
	connected_to: Name;
	instance: ConnectedInstance;
	override: boolean;

	constructor(
		Name: string,
		Value: ConnectedInstance[Name],
		ConnectToInstance: ConnectedInstance,
		InstancesPropertyName: Name,
		Override: boolean,
	) {
		super(Name, Value);

		this.instance = ConnectToInstance;
		this.instance[InstancesPropertyName] = this.value;
		this.connected_to = InstancesPropertyName;
		this.override = Override;

		this._janitor.Add(
			this.changed.Connect((new_value: ConnectedInstance[Name]) => {
				this.instance[InstancesPropertyName] = new_value;
			}),
		);
		this._janitor.Add(
			this.instance.GetPropertyChangedSignal<ConnectedInstance>(InstancesPropertyName).Connect(() => {
				if (!this.override) {
					this.Set(this.instance[InstancesPropertyName]);
				} else {
					this.instance[InstancesPropertyName] = this.Get();
				}
			}),
		);
	}
}
