import { Players, Workspace } from "@rbxts/services";
import { Character, CreateServer } from "shared/tver/exports";
import { Stun, Test } from "shared/tver/test/compound_effects_classes";
const server = CreateServer();
server.Start();
task.wait(2);
const stun = new Stun(true);
const plr = Players.GetPlayers()[0];
if (plr) {
	const char = plr.Character;
	const tver_char = char ? new Character(char) : undefined;
	const test_char = new Character(Workspace.FindFirstChild("Rig") as Model);

	if (tver_char !== undefined) {
		const test = new Test(tver_char);
		const test_applied = test.Applied;

		test_applied.SetDuration(5);
		print(test_applied.timer.GetLength());
		test_applied.Start();
	}
}
