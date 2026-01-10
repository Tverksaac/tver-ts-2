import { Component } from "../../core/component";

export abstract class CompoundEffect extends Component {
	Key: string = "CompoundEffect";

	GetState(): number {
		return 1;
	}
}
