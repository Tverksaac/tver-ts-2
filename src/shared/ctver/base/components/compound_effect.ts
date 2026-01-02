import { Component, UpdateRateEnum } from "../../core/component";

export abstract class CompoundEffect extends Component {
	Key: string = "CompoundEffect";
	UpdateRate: UpdateRateEnum = UpdateRateEnum.Custom;

	OnAttach(): void {
		print("atached");
	}
	OnDetach(): void {
		print("detached");
	}
	Update(): void {
		print("updated");
	}

	GetState(): number {
		return 1;
	}
}
