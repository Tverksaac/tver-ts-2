import { ConnectedStat, SeparatedStat } from "shared/ctver/fundamental/stat";
import { Component } from "../../core/component";

type StatReturns = {};

export abstract class Stat extends Component {
	Key: string = "Stat";

	abstract ConnectedStat:
		| ConnectedStat<Humanoid, ExtractKeys<WritableInstanceProperties<Humanoid>, number>>
		| SeparatedStat;

	OnAttach(): void {}
	OnDetach(): void {}
	Update(): void {}
	GetState(): StatReturns {
		return {};
	}
}
