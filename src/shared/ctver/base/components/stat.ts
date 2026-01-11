import { Janitor } from "@rbxts/janitor";
import { Component } from "../../core/component";
import { SeparatedStat } from "shared/ctver/fundamental/stat";
import { CreateSymbol } from "shared/ctver/fundamental/symbol";

type StatReturns = {};

export abstract class Stat extends Component {
	Key: string = "Stat";

	private _janitor = new Janitor();

	abstract PropertyToAffect: ExtractKeys<WritableInstanceProperties<Humanoid>, number>;
	protected Stat!: SeparatedStat;

	private Humanoid = this.Host.Humanoid;

	public Set(value: number): void {
		this.Stat.Base.Set(value);
	}

	s1 = CreateSymbol("");
	s2 = CreateSymbol("");
	s3 = CreateSymbol("");

	public OnConstruct(): void {
		this.AddOnAttachCallback(this.s1, () => {
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
		this.AddOnAttachCallback(this.s2, () => {
			print("attached");
		});
		this.AddOnAttachCallback(this.s3, () => {
			print("attached 2");
		});
		this.AddOnDetachCallback(this.s1, () => {
			this._janitor.Destroy();
			this.Destroy();
		});
	}

	public GetState(): StatReturns {
		return {};
	}
}
