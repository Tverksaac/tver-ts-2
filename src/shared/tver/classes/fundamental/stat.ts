//!native

import { Janitor } from "@rbxts/janitor";
import { SeparatedProperty } from "./property";
import { get_context_name, get_logger, is_client_context } from "shared/tver/utility/utils";

const LOG_KEY = "[STAT]";
const CONNECTED_TAG = "[TVER]" + LOG_KEY;
const dlog = get_logger(LOG_KEY, true);

function create_tag(name: string): string {
	return CONNECTED_TAG + `[${string.upper(get_context_name())}]` + " Connected to" + name;
}

function calculate_total_bonus(stat: SeparatedStat): number {
	const base = stat.Base.Get();
	const bonus_raw = stat.Bonus.Raw.Get();
	const bonus_modifier = stat.Bonus.Modifier.Get();

	return (base + bonus_raw) * bonus_modifier;
}

function update_total(stat: SeparatedStat): void {
	stat.Total.Set(calculate_total_bonus(stat));
}

/**
 * Numeric stat with base, bonus (raw/modifier), and total calculated value.
 */
export class SeparatedStat {
	protected janitor = new Janitor();

	readonly name: string;

	Base: SeparatedProperty<number>;
	Bonus: {
		Raw: SeparatedProperty<number>;
		Modifier: SeparatedProperty<number>;
	};
	Total: SeparatedProperty<number>;

	constructor(Name: string, Value: number) {
		this.name = Name;

		this.Base = new SeparatedProperty(Name + "_Base", Value);
		this.Bonus = {
			Raw: new SeparatedProperty(Name + "_Bonus_Raw", 0),
			Modifier: new SeparatedProperty(Name + "_Bonus_Modifier", 1),
		};
		this.Total = new SeparatedProperty(Name + "_Total", Value);

		this.janitor.Add(
			this.Base.changed.Connect(() => {
				update_total(this);
			}),
		);
		this.janitor.Add(
			this.Bonus.Raw.changed.Connect(() => {
				update_total(this);
			}),
		);
		this.janitor.Add(
			this.Bonus.Modifier.changed.Connect(() => {
				update_total(this);
			}),
		);
		this.janitor.Add(this.Base);
		this.janitor.Add(this.Bonus.Modifier);
		this.janitor.Add(this.Bonus.Raw);
		this.janitor.Add(this.Total);
	}

	/** Cleanup owned properties and connections. */
	public Destroy(): void {
		this.janitor.Destroy();
	}
}

/**
 * Stat bound to an Instance numeric property; updates the instance when total changes.
 */
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

		const tag = create_tag(tostring(Name));
		if (ConnectToInstance.HasTag(tag)) {
			this.Destroy();
			return;
		} else {
			ConnectToInstance.AddTag(tag);
		}

		type Indexable = ConnectedInstance[Name];
		this.instance[Name] = this.Total.Get() as Indexable;

		if (is_client_context()) return;
		this.janitor.Add(
			this.instance.GetPropertyChangedSignal(Name).Connect(() => {
				this.instance[Name] = this.Total.Get() as Indexable;
			}),
		);
		this.janitor.Add(
			this.Total.changed.Connect(() => {
				this.instance[Name] = this.Total.Get() as Indexable;
			}),
		);
	}
}
