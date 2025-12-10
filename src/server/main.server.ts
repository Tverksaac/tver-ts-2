import { Players, Workspace } from "@rbxts/services";
import { Character, CreateServer } from "shared/tver/exports";
import { Stun } from "shared/tver/test/compound_effects_classes";
const server = CreateServer();
server.Start();
task.wait(2);
const stun = new Stun(true);
const plr = Players.GetPlayers()[0];
if (plr) {
	const char = plr.Character;
	const tver_char = char ? new Character(char) : undefined;

	if (tver_char !== undefined) {
		stun.ApplyTo(tver_char, 5).Start();
	}
}
