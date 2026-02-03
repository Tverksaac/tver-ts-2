import { Janitor } from "@rbxts/janitor";
import { Component } from "../../core/component";
import { SeparatedStat } from "shared/ctver/fundamental/stat";
import { CreateSymbol } from "shared/ctver/fundamental/symbol";
import { UpdateRate } from "shared/ctver/utility/enums";

type StatReturns = {};

export abstract class Stat extends Component {
	/**
	 * @param PropertyToAffect UniqueKey property will be set to provided PropertyToAffect
	 */
	static Factory(PropertyToAffect: ExtractKeys<WritableInstanceProperties<Humanoid>, number>) {
		return class extends Stat {
			UniqueKey = PropertyToAffect;
			PropertyToAffect: ExtractKeys<WritableInstanceProperties<Humanoid>, number> = PropertyToAffect;
		};
	}

	Key: string = "Stat";

	private _janitor = new Janitor();

	abstract PropertyToAffect: ExtractKeys<WritableInstanceProperties<Humanoid>, number>;
	protected Stat!: SeparatedStat;

	public UpdateRate: UpdateRate = UpdateRate.Heartbeat;

	private Humanoid = this.Host.Humanoid;

	public Set(value: number): void {
		this.Stat.Base.Set(value);
	}

	public OnConstruct(): void {
		this.AddOnAttachCallback(CreateSymbol(""), () => {
			this.Stat = new SeparatedStat(this.UniqueKey + "_Stat", this.Humanoid[this.PropertyToAffect]);

			this._janitor.Add(
				this.Humanoid.GetPropertyChangedSignal(this.PropertyToAffect).Connect(() => {
					if (this.Humanoid[this.PropertyToAffect] === this.Stat.Total.Get()) return;
					this.Humanoid[this.PropertyToAffect] = this.Stat.Total.Get();
				}),
			);
			this._janitor.Add(
				this.Stat.Total.changed.Connect((new_val) => {
					if (this.Humanoid[this.PropertyToAffect] === new_val) return;
					this.Humanoid[this.PropertyToAffect] = new_val;
				}),
			);

			this.Humanoid[this.PropertyToAffect] = this.Stat.Total.Get();
		});
		this.AddOnDetachCallback(CreateSymbol(""), () => {
			this._janitor.Destroy();
		});
		this.AddOnUpdateCallback(CreateSymbol(""), () => {
			print(this.Humanoid[this.PropertyToAffect] + "_" + this.UniqueKey);
		});
	}

	public GetState(): StatReturns {
		return {};
	}
}
