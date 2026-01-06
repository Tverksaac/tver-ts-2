import { Component } from "../../core/component";

type StatReturns = {};

export abstract class Stat extends Component {
	Key: string = "Stat";

	abstract PropertyToAffect: ExtractKeys<WritableInstanceProperties<Humanoid>, number>;

	public OnAttach(): void {}
	public OnDetach(): void {}
	public Update(): void {
		this.UpdateCallback();
	}
	protected UpdateCallback(): void {}
	public GetState(): StatReturns {
		return {};
	}
}
