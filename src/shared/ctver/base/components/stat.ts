import { Component, UpdateRateEnum } from "../../core/component";

export abstract class Stat extends Component {
	Key: string = "Stat";
	UpdateRate: UpdateRateEnum = UpdateRateEnum.Custom;

	abstract Affects: string;

	OnAttach(): void {}
	OnDetach(): void {}
	Update(): void {}
	GetState(): {
		value: number;
	} {
		return {
			value: 52,
		};
	}
}
