import { UpdateRate } from "shared/ctver/utility/enums";
import { Stat } from "../components/stat";

export class StrengthStat extends Stat {
	UniqueKey = "Strength";
	PropertyToAffect?: ExtractKeys<WritableInstanceProperties<Humanoid>, number> | undefined;
	public UpdateRate = UpdateRate.Manual;
	protected InitialValue?: number | undefined = 2;

	public OnConstruct(): void {
		this.Stat.Total.changed.Connect((new_val, prev_val) => {
			const max_health_stat = this.Host.GetPort("StatManager").GetStat("MaxHealth")?.Stat;
			if (!max_health_stat) {
				warn("Max health stat was not found...");
				return;
			}
			let val_to_set = max_health_stat.Bonus.Modifier.Get() + (new_val - prev_val);
			max_health_stat.Bonus.Modifier.Set(val_to_set);
		});
	}
}
