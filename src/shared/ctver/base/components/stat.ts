import { Janitor } from "@rbxts/janitor";
import { Component } from "../../core/component";
import { SeparatedStat } from "shared/ctver/fundamental/stat";
import { Teams } from "@rbxts/services";

type StatReturns = {};

export abstract class Stat extends Component {
	Key: string = "Stat";

	private _janitor = new Janitor();

	abstract PropertyToAffect: ExtractKeys<WritableInstanceProperties<Humanoid>, number>;
	protected Stat!: SeparatedStat;

	private Humanoid = this.Host().Humanoid;

	public Set(value: number): void {
		this.Stat.Base.Set(value);
	}

	public OnAttach(): void {
		this.Stat = new SeparatedStat(this.UniqueKey + "_Stat", 10);

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
	}
	public OnDetach(): void {
		this._janitor.Destroy();
		this.Destroy();
	}
	public Update(): void {
		this.UpdateCallback();
	}
	protected UpdateCallback(): void {}

	public GetState(): StatReturns {
		return {};
	}
}
