//!native

import { Janitor } from "@rbxts/janitor";
import { SeparatedProperty } from "./property";
import { dwlog, get_logger, is_client_context } from "shared/tver/utility/utils";

const LOG_KEY = "[STAT]"
const CONNECTED_TAG = "[TVER]" + LOG_KEY + " Connected to "
const dlog = get_logger(LOG_KEY, true)

function calculate_total_bonus(stat: SeparatedStat): number {
	const base = stat.Base.Get();
	const bonus_raw = stat.Bonus.Raw.Get();
	const bonus_modifer = stat.Bonus.Modifer.Get();

	return (base + bonus_raw) * bonus_modifer;
}

function update_total(stat: SeparatedStat): void {
	dlog.w(stat.name + " updated to " + calculate_total_bonus(stat))
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
				dlog.w("Modifer for " + this.name + " changed to " + this.Bonus.Modifer.Get())
				update_total(this);
			}),
		);
		this._janitor.Add(this.Base);
		this._janitor.Add(this.Bonus.Modifer);
		this._janitor.Add(this.Bonus.Raw);
		this._janitor.Add(this.Total);
	}

	public getType() {
		return "SeparatedStat"
	}

	public Destroy() {
		this._janitor.Destroy();
	}
}

export class ConnectedStat<
	ConnectedInstance extends Instance,
	Name extends ExtractKeys<WritableInstanceProperties<ConnectedInstance>, number>,
> extends SeparatedStat {
	instance: ConnectedInstance;
	conected_to: Name;

	constructor(ConnectToInstance: ConnectedInstance, Name: Name, Value: number) {
		super(tostring(Name), Value);
		this.instance = ConnectToInstance;
		this.conected_to = Name;
		
		if (ConnectToInstance.HasTag(CONNECTED_TAG + tostring(Name))) {
			this.Destroy()
			return
		} else {
			ConnectToInstance.AddTag(CONNECTED_TAG + tostring(Name))
		}

		type Indexable = ConnectedInstance[Name];
		this.instance[Name] = this.Total.Get() as Indexable;

		if (is_client_context()) return
		this._janitor.Add(
			this.Total.changed.Connect(() => {
				this.instance[Name] = this.Total.Get() as Indexable;
			}),
		);
		this._janitor.Add(
			this.instance.GetPropertyChangedSignal(Name).Connect(() => {
				this.instance[Name] = this.Total.Get() as Indexable;
			}),
		);
	}

	public getType(): string {
		return "ConnectedStat"
	}
}