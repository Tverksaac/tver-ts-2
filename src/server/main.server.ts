import { Players } from "@rbxts/services";
import { Character } from "shared/ctver/core/character";

task.wait(5);
const plr = Players.GetPlayers()[0];
if (plr) {
	const char = plr.Character;
	const tver_char = (char ? new Character(char) : undefined) as Character;
	const sm = tver_char.GetPort("StatManager");
	sm.GetStat("WalkSpeed")?.Set(10);
}
