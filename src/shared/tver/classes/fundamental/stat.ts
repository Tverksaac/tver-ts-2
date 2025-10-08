import { Janitor } from "@rbxts/janitor";
import { SeparatedProperty } from "./property";
import { is_client_context } from "shared/tver/utility/utils";

function calculate_total_bonus(stat: SeparatedStat): number {
	const base = stat.Base.Get();
	const bonus_raw = stat.Bonus.Raw.Get();
	const bonus_modifer = stat.Bonus.Modifer.Get();

	return (base + bonus_raw) * bonus_modifer;
}

function update_total(stat: SeparatedStat): void {
	stat.Total.Set(calculate_total_bonus(stat));
}

export class SeparatedStat {
	protected _janitor = new Janitor();

	readonly name: string;

	Base: SeparatedProperty<number>;
	Bonus: {
		Raw: SeparatedProperty<number>;
		Modifer: SeparatedProperty<number>;
	};
	Total: SeparatedProperty<number>;

	constructor(Name: string, Value: number) {
		this.name = Name;

		this.Base = new SeparatedProperty(Name + "_Base", Value);
		this.Bonus = {
			Raw: new SeparatedProperty(Name + "_Bonus_Raw", 0),
			Modifer: new SeparatedProperty(Name + "_Bonus_Modifer", 1),
		};
		this.Total = new SeparatedProperty(Name + "_Total", Value);

		this._janitor.Add(
			this.Base.changed.Connect(() => {
				update_total(this);
			}),
		);
		this._janitor.Add(
			this.Bonus.Raw.changed.Connect(() => {
				update_total(this);
			}),
		);
		this._janitor.Add(
			this.Bonus.Modifer.changed.Connect(() => {
				update_total(this);
			}),
		);
		this._janitor.Add(this.Base);
		this._janitor.Add(this.Bonus.Modifer);
		this._janitor.Add(this.Bonus.Raw);
		this._janitor.Add(this.Total);
	}

	Destroy() {
		this._janitor.Cleanup();
		this._janitor.Destroy();
	}
}

export class ConnectedStat<
	ConnectedInstance extends Instance,
	Name extends ExtractKeys<WritableInstanceProperties<ConnectedInstance>, number>,
> extends SeparatedStat {
	instance: ConnectedInstance;
	conected_to: Name;

	constructor(Name: string, Value: number, ConnectToInstance: ConnectedInstance, InstancePropertyName: Name) {
		super(Name, Value);

		this.instance = ConnectToInstance;
		type Indexable = ConnectedInstance[Name];

		print("SET")
		this.instance[InstancePropertyName] = this.Total.Get() as Indexable;
		this.conected_to = InstancePropertyName;
		
		//test reasons
		print(is_client_context())
		if (is_client_context()) return
		print("NOT CLIENT")
		this._janitor.Add(
			this.Total.changed.Connect(() => {
				this.instance[InstancePropertyName] = this.Total.Get() as Indexable;
			}),
		);
		this._janitor.Add(
			this.instance.GetPropertyChangedSignal(InstancePropertyName).Connect(() => {
				print(this.Total.Get())
				this.instance[InstancePropertyName] = this.Total.Get() as Indexable;
			}),
		);
	}
}