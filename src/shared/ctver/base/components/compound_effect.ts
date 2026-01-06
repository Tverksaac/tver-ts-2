import { Component } from "../../core/component";

export abstract class CompoundEffect extends Component {
	Key: string = "CompoundEffect";

	OnAttach(): void {
		print("attached");
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
